from datetime import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from grizzl_e.client import Client
from grizzl_e.document import Document
from grizzl_e.managers.tariffs import (
    TariffState,
    TariffManager,
    _doc_to_tariff_state,
    _find_overlaps,
)
from grizzl_e.types import Rate, TimeRange


class TestFindOverlaps:
    def test_no_overlaps(self):
        rates = [
            Rate("rate2", Decimal("0.25"), TimeRange(time(9, 0), time(12, 0))),
            Rate("rate3", Decimal("0.18"), TimeRange(time(14, 0), time(17, 0))),
        ]
        assert _find_overlaps(rates) == []

    def test_partial_overlap(self):
        rates = [
            Rate("rate2", Decimal("0.25"), TimeRange(time(9, 0), time(12, 0))),
            Rate("rate3", Decimal("0.18"), TimeRange(time(11, 0), time(14, 0))),
        ]
        conflicts = _find_overlaps(rates)
        assert len(conflicts) == 1
        assert conflicts[0].rates == ("rate2", "rate3")

    def test_exact_boundary_no_conflict(self):
        rates = [
            Rate("rate2", Decimal("0.25"), TimeRange(time(9, 0), time(12, 0))),
            Rate("rate3", Decimal("0.18"), TimeRange(time(12, 0), time(14, 0))),
        ]
        assert _find_overlaps(rates) == []

    def test_three_rates_middle_overlaps_both(self):
        rates = [
            Rate("rate2", Decimal("0.25"), TimeRange(time(9, 0), time(15, 0))),
            Rate("rate3", Decimal("0.18"), TimeRange(time(13, 0), time(17, 0))),
            Rate("rate4", Decimal("0.30"), TimeRange(time(14, 0), time(18, 0))),
        ]
        conflicts = _find_overlaps(rates)
        assert len(conflicts) == 3  # all pairs overlap

    def test_disabled_rate_no_conflict(self):
        rates = [
            Rate("rate2", Decimal("0.25"), TimeRange(time(12, 0), time(12, 0))),
            Rate("rate3", Decimal("0.18"), TimeRange(time(9, 0), time(17, 0))),
        ]
        assert _find_overlaps(rates) == []


class TestDocToTariffState:
    def _make_doc(
        self,
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

    def test_both_rates_enabled(self):
        doc = self._make_doc()
        state = _doc_to_tariff_state(doc)
        assert state.primary == Decimal("36")
        assert state.rate2 is not None
        assert state.rate2.value == Decimal("36")
        assert state.rate2.time_range.lower == time(16, 0)
        assert state.rate2.time_range.upper == time(20, 0)
        assert state.rate3 is not None
        assert state.rate3.value == Decimal("3")
        assert state.rate3.time_range.lower == time(0, 0)
        assert state.rate3.time_range.upper == time(6, 0)

    def test_rate2_disabled(self):
        doc = self._make_doc(tarifAEnable=0)
        state = _doc_to_tariff_state(doc)
        assert state.rate2 is None

    def test_rate3_disabled(self):
        doc = self._make_doc(tarifBEnable=0)
        state = _doc_to_tariff_state(doc)
        assert state.rate3 is None

    def test_rate_zero_times_disabled(self):
        doc = self._make_doc(tarifAStart=0, tarifAStop=0)
        state = _doc_to_tariff_state(doc)
        assert state.rate2 is None

    def test_overlapping_rates_detected(self):
        # rate2: 16:00-20:00, rate3: 18:00-22:00 → overlap 18:00-20:00
        doc = self._make_doc(tarifAStart=960, tarifAStop=1200, tarifBStart=1080, tarifBStop=1320)
        state = _doc_to_tariff_state(doc)
        assert len(state.conflicts) == 1
        assert state.conflicts[0].rates == ("rate2", "rate3")


class TestTariffManager:
    @pytest.fixture
    def mock_client(self):
        client = AsyncMock(spec=Client)
        client.get_document = AsyncMock()
        client.set_many = AsyncMock()
        return client

    async def test_get_returns_state(self, mock_client):
        mock_client.get_document.return_value = _make_doc_for_validator()
        validator = TariffManager(mock_client)
        state = await validator.get()
        assert isinstance(state, TariffState)
        mock_client.get_document.assert_called_once()

    async def test_set_succeeds_no_overlap(self, mock_client):
        rate2 = Rate("rate2", Decimal("0.25"), TimeRange(time(9, 0), time(12, 0)))
        rate3 = Rate("rate3", Decimal("0.18"), TimeRange(time(14, 0), time(17, 0)))
        validator = TariffManager(mock_client)
        await validator.set_rates(rate2, rate3)
        await validator.set_primary(Decimal("0.12"))
        calls = [c.kwargs for c in mock_client.set_many.call_args_list]
        rates_call = calls[0]
        assert rates_call["tarifAEnable"] == 1
        assert rates_call["tarifAValue"] == 0  # int(Decimal("0.25")) == 0
        assert rates_call["tarifAStart"] == 540
        assert rates_call["tarifAStop"] == 720
        assert rates_call["tarifBEnable"] == 1
        assert rates_call["tarifBValue"] == 0  # int(Decimal("0.18")) == 0
        assert rates_call["tarifBStart"] == 840
        assert rates_call["tarifBStop"] == 1020
        primary_call = calls[1]
        assert primary_call["tarif"] == 0  # int(Decimal("0.12")) == 0

    async def test_set_raises_on_overlap(self, mock_client):
        rate2 = Rate("rate2", Decimal("0.25"), TimeRange(time(9, 0), time(12, 0)))
        rate3 = Rate("rate3", Decimal("0.18"), TimeRange(time(11, 0), time(14, 0)))
        validator = TariffManager(mock_client)
        with pytest.raises(ValueError, match="overlap"):
            await validator.set_rates(rate2, rate3)
        # Should not write anything when validation fails
        mock_client.set_many.assert_not_called()

    async def test_set_with_only_rate2(self, mock_client):
        rate2 = Rate("rate2", Decimal("0.25"), TimeRange(time(9, 0), time(12, 0)))
        validator = TariffManager(mock_client)
        await validator.set_rates(rate2)
        call_data = mock_client.set_many.call_args.kwargs
        assert call_data["tarifAEnable"] == 1
        assert call_data["tarifBEnable"] == 0  # rate 3 disabled


def _make_doc_for_validator():
    """Minimal Document for TariffManager tests."""
    return Document(
        verFWMain="test", verFWWifi="test", serialNumCPU="", serialNum="test",
        fwCRC32="test", verFWStatus=1, pilot=0, state=2, subState=5,
        currentSet=32, curDesign=40, minCurrent=7, minVoltage=175,
        gridRange=0, typeEvse=1, typeRelay=0, aiModecurrent=7, aiStatus=0,
        aiVoltage=200, aiVoltageStart=0, aiVoltageDrop=0, aiPowerDrop=0,
        aiMode=0, SNflag=0, ground=1, groundCtrl=1, tarif=12,
        activeTarif=1, tarifAEnable=1, tarifBEnable=1,
        tarifAValue=36, tarifBValue=3,
        tarifAStart=960, tarifAStop=1200,
        tarifBStart=0, tarifBStop=360,
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
