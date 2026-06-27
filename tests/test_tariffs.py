from datetime import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from grizzl_e.client import Client
from grizzl_e.device import BaseDevice
from grizzl_e.document import Document
from grizzl_e.managers.tariffs import (
    Rate,
    TariffState,
    TariffsManager,
    WraparoundTimeRange,
)


class TestRateMutateFrom:
    def test_mutate_from_updates_values(self):
        old = Rate(value=10, is_enabled=True)
        new = Rate(value=20, is_enabled=False)
        old.mutate_from(new)
        assert old.value == 20
        assert old.is_enabled is False

    def test_mutate_from_no_changes(self):
        old = Rate(value=10, is_enabled=True)
        new = Rate(value=10, is_enabled=True)
        old.mutate_from(new)
        assert old.value == 10
        assert old.is_enabled is True


class TestTariffStateMutateFrom:
    def test_mutate_from_updates_all_rates(self):
        old = TariffState(
            primary_rate=Rate(value=12),
            rate2=Rate(value=20, time_range=WraparoundTimeRange(time(9, 0), time(12, 0))),
            rate3=Rate(value=30, time_range=WraparoundTimeRange(time(14, 0), time(17, 0))),
        )
        new = TariffState(
            primary_rate=Rate(value=15),
            rate2=Rate(value=25, time_range=WraparoundTimeRange(time(9, 0), time(12, 0))),
            rate3=Rate(value=35, time_range=WraparoundTimeRange(time(14, 0), time(17, 0))),
        )
        old.mutate_from(new)
        assert old.primary_rate.value == 15
        assert old.rate2 and old.rate2.value == 25
        assert old.rate3 and old.rate3.value == 35

    def test_mutate_from_enables_disabled_rate(self):
        old = TariffState(primary_rate=Rate(value=12))
        new = TariffState(
            primary_rate=Rate(value=12),
            rate2=Rate(value=20),
        )
        old.mutate_from(new)
        assert old.rate2 is not None
        assert old.rate2.value == 20
        assert "rate2" in old.changed_fields

    def test_mutate_from_enables_disabled_rate(self):
        old = TariffState(primary_rate=Rate(value=12))
        new = TariffState(
            primary_rate=Rate(value=12),
            rate2=Rate(value=20),
        )
        old.mutate_from(new)
        assert old.rate2 is not None
        assert old.rate2.value == 20

    def test_mutate_from_disables_rate(self):
        old = TariffState(
            primary_rate=Rate(value=12),
            rate2=Rate(value=20),
        )
        new = TariffState(primary_rate=Rate(value=12))
        old.mutate_from(new)
        assert old.rate2 is None


class TestTariffStateValidate:
    def test_no_conflict_non_overlapping(self):
        state = TariffState(
            primary_rate=Rate(value=12),
            rate2=Rate(value=20, time_range=WraparoundTimeRange(time(9, 0), time(12, 0))),
            rate3=Rate(value=30, time_range=WraparoundTimeRange(time(14, 0), time(17, 0))),
        )
        state.validate()  # should not raise

    def test_conflict_overlapping(self):
        state = TariffState(
            primary_rate=Rate(value=12),
            rate2=Rate(value=20, time_range=WraparoundTimeRange(time(9, 0), time(12, 0))),
            rate3=Rate(value=30, time_range=WraparoundTimeRange(time(11, 0), time(14, 0))),
        )
        with pytest.raises(ExceptionGroup, match="Tariff time range conflicts"):
            state.validate()

    def test_disabled_rate_does_not_conflict(self):
        state = TariffState(
            primary_rate=Rate(value=12),
            rate2=Rate(value=20, time_range=WraparoundTimeRange(time(9, 0), time(12, 0)), is_enabled=False),
            rate3=Rate(value=30, time_range=WraparoundTimeRange(time(11, 0), time(14, 0))),
        )
        state.validate()  # rate2 is disabled, so no conflict


class TestTariffsManager:
    @pytest.fixture
    def mock_client(self):
        client = AsyncMock(spec=Client)
        client.get_document = AsyncMock()
        client.set_many = AsyncMock()
        return client

    @pytest.fixture
    def mock_device(self, mock_client):
        doc = _make_doc_for_manager()
        mock_client.document = doc
        device = MagicMock(spec=BaseDevice)
        device.client = mock_client
        return device

    def test_initializes_state_from_document(self, mock_device):
        mgr = TariffsManager(mock_device)
        assert isinstance(mgr.state, TariffState)
        assert mgr.state.primary_rate.value == 12

    def test_on_fields_changed_mutates_state_in_place(self, mock_device):
        mgr = TariffsManager(mock_device)
        old_state = mgr.state
        old_rate2 = mgr.state.rate2

        doc = _make_doc_for_manager(tarifAStart=1200, tarifAStop=1320)  # 20:00-22:00
        mgr.on_fields_changed(doc, mgr.fields)

        # Same object identity
        assert mgr.state is old_state
        assert mgr.state.rate2 is old_rate2
        # But values changed
        assert mgr.state.rate2 and mgr.state.rate2.time_range.lower == time(20, 0)

    def test_on_fields_changed_collects_validation_errors(self, mock_device):
        mgr = TariffsManager(mock_device)
        # rate2: 16:00-20:00, rate3: 18:00-22:00 → overlap
        doc = _make_doc_for_manager(tarifAStart=960, tarifAStop=1200, tarifBStart=1080, tarifBStop=1320)
        mgr.on_fields_changed(doc, mgr.fields)

        assert mgr.in_exception_state
        assert len(mgr.exceptions) == 1

    def test_on_fields_changed_clears_errors_on_success(self, mock_device):
        mgr = TariffsManager(mock_device)
        # First call with overlapping rates
        doc = _make_doc_for_manager(tarifAStart=960, tarifAStop=1200, tarifBStart=1080, tarifBStop=1320)
        mgr.on_fields_changed(doc, mgr.fields)
        assert mgr.in_exception_state

        # Second call with non-overlapping rates
        doc = _make_doc_for_manager(tarifAStart=960, tarifAStop=1200, tarifBStart=1320, tarifBStop=1400)  # 22:00-23:20
        mgr.on_fields_changed(doc, mgr.fields)
        assert not mgr.in_exception_state
        assert len(mgr.exceptions) == 0


def _make_doc_for_manager(
    tarif=12,
    tarifAEnable=1,
    tarifBEnable=1,
    tarifAValue=36,
    tarifBValue=3,
    tarifAStart=960,
    tarifAStop=1200,
    tarifBStart=0,
    tarifBStop=360,
):
    return Document(
        verFWMain="test", verFWWifi="test", serialNumCPU="", serialNum="test",
        fwCRC32="test", verFWStatus=1, pilot=0, state=2, subState=5,
        currentSet=32, curDesign=40, minCurrent=7, minVoltage=175,
        gridRange=0, typeEvse=1, typeRelay=0, aiModecurrent=7, aiStatus=0,
        aiVoltage=200, aiVoltageStart=0, aiVoltageDrop=0, aiPowerDrop=0,
        aiMode=0, SNflag=0, ground=1, groundCtrl=1, tarif=tarif,
        activeTarif=1, tarifAEnable=tarifAEnable, tarifBEnable=tarifBEnable,
        tarifAValue=tarifAValue, tarifBValue=tarifBValue,
        tarifAStart=tarifAStart, tarifAStop=tarifAStop,
        tarifBStart=tarifBStart, tarifBStop=tarifBStop,
        timerType=0, timeZone=-5, systemTime=0, timeMsg=0,
        timeLimitS=0, energyLimitS=0, moneyLimitS=0, evseEnabled=0,
        suspendErrors=0, suspendLimits=0, oneCharge=0, delayedLimit=0,
        timeLimit=0, energyLimit=0, moneyLimit=0,
        sh1Enabled=1, sh1Start=0, sh1Stop=360, sh1CurrentEnable=0,
        sh1CurrentValue=12, sh1EnergyEnable=0, sh1EnergyValue=3,
        sh2Enabled=0, sh2Start=0, sh2Stop=0, sh2CurrentEnable=0,
        sh2CurrentValue=12, sh2EnergyEnable=0, sh2EnergyValue=0,
        totalEnergy=0, sessionTime=0, sessionEnergy=0, sessionMoney=0,
        sessionStarted=0, IEM1=0, IEM2=0, IEM1_money=0, IEM2_money=0,
        curMeas1=0, curMeas2=0, curMeas3=0, voltMeas1=241, voltMeas2=0,
        voltMeas3=0, powerMeas=0, temperature1=34, temperature2=34,
        leakValue=15, leakValueH=13, vBat=2.86, adapter=255,
        scanComplete=0, ocppconnected=0, ocppEnabled=0, ocppOfflineAva=1,
        STA_IP_Addres="192.168.1.1", RSSI=-62, logReady=1, lang=1,
        ssidNameAP="GRU-L0000310350", ssidPasswordAP="",
        ssidName="The Coop", ssidPassword="",
        httpUsername="", httpPassword="",
        WifiMode=3, ESP_MAC="B4:8A:0A:8A:4E:10",
        mac_bind=0, STA_MAC="",
    )
