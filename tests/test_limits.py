import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from grizzl_e.client import Client
from grizzl_e.managers.limits import LimitState, LimitsManager


def _doc_with_limits(
    time_limit: int = 3600,
    energy_limit: int = 10,
    money_limit: int = 50,
    suspend_limits: int = 0,
):
    data = {
        "verFWMain": "test", "verFWWifi": "test", "serialNumCPU": "",
        "serialNum": "test", "fwCRC32": "test", "verFWStatus": 1,
        "pilot": 0, "state": 2, "subState": 5, "currentSet": 32,
        "curDesign": 40, "minCurrent": 7, "minVoltage": 175,
        "gridRange": 0, "typeEvse": 1, "typeRelay": 0,
        "aiModecurrent": 7, "aiStatus": 0, "aiVoltage": 200,
        "aiVoltageStart": 0, "aiVoltageDrop": 0, "aiPowerDrop": 0,
        "aiMode": 0, "SNflag": 0, "ground": 1, "groundCtrl": 1,
        "tarif": 12, "activeTarif": 1, "tarifAEnable": 1,
        "tarifBEnable": 1, "tarifAValue": 36, "tarifBValue": 3,
        "tarifAStart": 960, "tarifAStop": 1200, "tarifBStart": 0,
        "tarifBStop": 360, "timerType": 0, "timeZone": -5,
        "systemTime": 0, "timeMsg": 0, "timeLimitS": 0,
        "energyLimitS": 0, "moneyLimitS": 0, "evseEnabled": 0,
        "suspendErrors": 0, "suspendLimits": suspend_limits,
        "oneCharge": 0, "delayedLimit": 0, "timeLimit": time_limit,
        "energyLimit": energy_limit, "moneyLimit": money_limit,
        "sh1Enabled": 1, "sh1Start": 0, "sh1Stop": 360,
        "sh1CurrentEnable": 0, "sh1CurrentValue": 12,
        "sh1EnergyEnable": 0, "sh1EnergyValue": 3, "sh2Enabled": 0,
        "sh2Start": 0, "sh2Stop": 0, "sh2CurrentEnable": 0,
        "sh2CurrentValue": 12, "sh2EnergyEnable": 0,
        "sh2EnergyValue": 0, "totalEnergy": 0, "sessionTime": 0,
        "sessionEnergy": 0, "sessionMoney": 0, "sessionStarted": 0,
        "IEM1": 0, "IEM2": 0, "IEM1_money": 0, "IEM2_money": 0,
        "curMeas1": 0, "curMeas2": 0, "curMeas3": 0, "voltMeas1": 241,
        "voltMeas2": 0, "voltMeas3": 0, "powerMeas": 0,
        "temperature1": 34, "temperature2": 34, "leakValue": 15,
        "leakValueH": 13, "vBat": 2.86, "adapter": 255,
        "scanComplete": 0, "ocppconnected": 0, "ocppEnabled": 0,
        "ocppOfflineAva": 1, "STA_IP_Addres": "192.168.1.1", "RSSI": -62,
        "logReady": 1, "lang": 1,
        "ssidNameAP": "GRU-L0000310350", "ssidPasswordAP": "",
        "ssidName": "The Coop", "ssidPassword": "",
        "httpUsername": "", "httpPassword": "",
        "WifiMode": 3, "ESP_MAC": "B4:8A:0A:8A:4E:10",
        "mac_bind": 0, "STA_MAC": "",
    }
    return data


@pytest.fixture
def mock_session():
    post_mock = AsyncMock()
    post_mock.return_value.raise_for_status = AsyncMock()
    post_mock.return_value.json = AsyncMock(return_value=_doc_with_limits())

    session = AsyncMock()
    session.post = post_mock
    session.closed = False
    return session


@pytest.fixture
def client(mock_session, tmp_path):
    state_file = tmp_path / "state.pkl"
    return Client("http://192.168.1.1", session=mock_session, state_file=state_file)


class TestGetState:
    async def test_returns_current_limits(self, client, mock_session):
        await client.refresh()
        client._document = None
        mock_session.post.return_value.json = AsyncMock(
            return_value=_doc_with_limits(time_limit=100, energy_limit=200, money_limit=300, suspend_limits=1)
        )
        state = await client.device.limits.get_state()
        assert state.time == 100
        assert state.energy == 200
        assert state.money == 300
        assert state.suspended is True

    async def test_not_suspended(self, client, mock_session):
        await client.refresh()
        client._document = None
        mock_session.post.return_value.json = AsyncMock(
            return_value=_doc_with_limits(suspend_limits=0)
        )
        state = await client.device.limits.get_state()
        assert state.suspended is False


class TestSuspend:
    async def test_saves_state_and_writes_zeroes(self, client, mock_session):
        await client.refresh()
        client._document = None
        mock_session.post.return_value.json = AsyncMock(
            return_value=_doc_with_limits(time_limit=3600, energy_limit=10, money_limit=50)
        )
        await client.device.limits.suspend()
        call_data = mock_session.post.call_args.kwargs["data"]
        assert call_data["suspendLimits"] == 1
        assert call_data["timeLimit"] == 0
        assert call_data["energyLimit"] == 0
        assert call_data["moneyLimit"] == 0

    async def test_state_persisted_to_file(self, client, mock_session, tmp_path):
        await client.refresh()
        client._document = None
        mock_session.post.return_value.json = AsyncMock(
            return_value=_doc_with_limits(time_limit=100, energy_limit=200, money_limit=300)
        )
        await client.device.limits.suspend()
        state = client.load_state(LimitsManager._STATE_KEY)
        assert state.time == 100
        assert state.energy == 200
        assert state.money == 300


class TestResume:
    async def test_restores_saved_limits(self, client, mock_session):
        await client.refresh()
        client._document = None
        mock_session.post.return_value.json = AsyncMock(
            return_value=_doc_with_limits(time_limit=100, energy_limit=200, money_limit=300)
        )
        await client.device.limits.suspend()
        mock_session.post.reset_mock()
        await client.device.limits.resume()
        call_data = mock_session.post.call_args.kwargs["data"]
        assert call_data["suspendLimits"] == 0
        assert call_data["timeLimit"] == 100
        assert call_data["energyLimit"] == 200
        assert call_data["moneyLimit"] == 300

    async def test_resume_without_suspend_raises(self, client, mock_session):
        await client.refresh()
        mock_session.post.return_value.json = AsyncMock(return_value=_doc_with_limits())
        with pytest.raises(KeyError):
            await client.device.limits.resume()

    async def test_resume_with_corrupted_state_raises(self, client, mock_session, tmp_path):
        state_file = tmp_path / "state.pkl"
        c = Client("http://192.168.1.1", session=mock_session, state_file=state_file)
        c.save_state(LimitsManager._STATE_KEY, "not a LimitState")
        with pytest.raises(RuntimeError, match="corrupted"):
            await c.device.limits.resume()


class TestSaveLoadState:
    async def test_save_without_state_file_raises(self, mock_session):
        c = Client("http://192.168.1.1", session=mock_session)
        with pytest.raises(RuntimeError, match="No state_file"):
            c.save_state("key", "value")

    async def test_load_without_state_file_raises(self, mock_session):
        c = Client("http://192.168.1.1", session=mock_session)
        with pytest.raises(RuntimeError, match="No state_file"):
            c.load_state("key")

    async def test_load_missing_key_raises(self, client, mock_session):
        mock_session.post.return_value.json = AsyncMock(return_value=_doc_with_limits())
        with pytest.raises(KeyError):
            client.load_state("nonexistent")

    async def test_save_and_load(self, client, mock_session):
        mock_session.post.return_value.json = AsyncMock(return_value=_doc_with_limits())
        client.save_state("custom", 42)
        assert client.load_state("custom") == 42
