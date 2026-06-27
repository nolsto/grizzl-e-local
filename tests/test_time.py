from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

import pytest

from grizzl_e.client import Client


def _doc_with_time(time_zone: int = -5, system_time: int = 1753986403):
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
        "tarifBStop": 360, "timerType": 0, "timeZone": time_zone,
        "systemTime": system_time, "timeMsg": 0, "timeLimitS": 0,
        "energyLimitS": 0, "moneyLimitS": 0, "evseEnabled": 0,
        "suspendErrors": 0, "suspendLimits": 0, "oneCharge": 0,
        "delayedLimit": 0, "timeLimit": 0, "energyLimit": 0,
        "moneyLimit": 0, "sh1Enabled": 1, "sh1Start": 0, "sh1Stop": 360,
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
    post_mock.return_value.json = AsyncMock(return_value=_doc_with_time())

    session = AsyncMock()
    session.post = post_mock
    session.closed = False
    return session


@pytest.fixture
def client(mock_session):
    return Client("http://192.168.1.1", session=mock_session)


class TestGetTime:
    async def test_returns_timezone_aware_datetime(self, client, mock_session):
        await client.refresh()
        client._document = None
        mock_session.post.return_value.json = AsyncMock(
            return_value=_doc_with_time(time_zone=-5, system_time=1753986403)
        )
        dt = await client.device.time.get_time()
        assert dt.tzinfo is not None
        assert dt.utcoffset() == timedelta(hours=-5)

    async def test_positive_timezone_offset(self, client, mock_session):
        await client.refresh()
        client._document = None
        mock_session.post.return_value.json = AsyncMock(
            return_value=_doc_with_time(time_zone=5, system_time=0)
        )
        dt = await client.device.time.get_time()
        assert dt.utcoffset() == timedelta(hours=5)

    async def test_utc_timezone(self, client, mock_session):
        await client.refresh()
        client._document = None
        mock_session.post.return_value.json = AsyncMock(
            return_value=_doc_with_time(time_zone=0, system_time=1000000)
        )
        dt = await client.device.time.get_time()
        assert dt.utcoffset() == timedelta(0)


class TestSetTime:
    async def test_sets_timezone_and_timestamp(self, client, mock_session):
        await client.refresh()
        tz = timezone(timedelta(hours=-5))
        dt = datetime(2025, 8, 1, 12, 0, 0, tzinfo=tz)
        await client.device.time.set_time(dt)
        call_data = mock_session.post.call_args.kwargs["data"]
        assert call_data["timeZone"] == -5
        assert call_data["systemTime"] == int(dt.timestamp())

    async def test_naive_datetime_raises(self, client, mock_session):
        dt = datetime(2025, 8, 1, 12, 0, 0)
        with pytest.raises(ValueError, match="timezone-aware"):
            await client.device.time.set_time(dt)

    async def test_different_timezones(self, client, mock_session):
        tz = timezone(timedelta(hours=3))
        dt = datetime(2025, 8, 1, 12, 0, 0, tzinfo=tz)
        await client.device.time.set_time(dt)
        call_data = mock_session.post.call_args.kwargs["data"]
        assert call_data["timeZone"] == 3
