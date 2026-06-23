"""Tests for NetworkManager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grizzl_e.client import Client
from grizzl_e.managers.network import NetworkManager


def _doc_with_network(**overrides):
    """Build a minimal document dict with network fields, then override."""
    base = {
        "verFWMain": "test",
        "verFWWifi": "test",
        "serialNumCPU": "",
        "serialNum": "test",
        "fwCRC32": "test",
        "verFWStatus": 1,
        "pilot": 0,
        "state": 2,
        "subState": 5,
        "currentSet": 32,
        "curDesign": 40,
        "minCurrent": 7,
        "minVoltage": 175,
        "gridRange": 0,
        "typeEvse": 1,
        "typeRelay": 0,
        "aiModecurrent": 7,
        "aiStatus": 0,
        "aiVoltage": 200,
        "aiVoltageStart": 0,
        "aiVoltageDrop": 0,
        "aiPowerDrop": 0,
        "aiMode": 0,
        "SNflag": 0,
        "ground": 1,
        "groundCtrl": 1,
        "tarif": 12,
        "activeTarif": 1,
        "tarifAEnable": 1,
        "tarifBEnable": 1,
        "tarifAValue": 36,
        "tarifBValue": 3,
        "tarifAStart": 960,
        "tarifAStop": 1200,
        "tarifBStart": 0,
        "tarifBStop": 360,
        "timerType": 0,
        "timeZone": -5,
        "systemTime": 0,
        "timeMsg": 0,
        "timeLimitS": 0,
        "energyLimitS": 0,
        "moneyLimitS": 0,
        "evseEnabled": 0,
        "suspendErrors": 0,
        "suspendLimits": 0,
        "oneCharge": 0,
        "delayedLimit": 0,
        "timeLimit": 0,
        "energyLimit": 0,
        "moneyLimit": 0,
        "sh1Enabled": 1,
        "sh1Start": 0,
        "sh1Stop": 360,
        "sh1CurrentEnable": 0,
        "sh1CurrentValue": 12,
        "sh1EnergyEnable": 0,
        "sh1EnergyValue": 3,
        "sh2Enabled": 0,
        "sh2Start": 0,
        "sh2Stop": 0,
        "sh2CurrentEnable": 0,
        "sh2CurrentValue": 12,
        "sh2EnergyEnable": 0,
        "sh2EnergyValue": 0,
        "totalEnergy": 0,
        "sessionTime": 0,
        "sessionEnergy": 0,
        "sessionMoney": 0,
        "sessionStarted": 0,
        "IEM1": 0,
        "IEM2": 0,
        "IEM1_money": 0,
        "IEM2_money": 0,
        "curMeas1": 0,
        "curMeas2": 0,
        "curMeas3": 0,
        "voltMeas1": 241,
        "voltMeas2": 0,
        "voltMeas3": 0,
        "powerMeas": 0,
        "temperature1": 34,
        "temperature2": 34,
        "leakValue": 15,
        "leakValueH": 13,
        "vBat": 2.86,
        "adapter": 255,
        "scanComplete": 0,
        "ocppconnected": 0,
        "ocppEnabled": 0,
        "ocppOfflineAva": 1,
        "STA_IP_Addres": "192.168.1.1",
        "RSSI": -62,
        "logReady": 1,
        "lang": 1,
        "ssidNameAP": "MyAP",
        "ssidPasswordAP": "ap123456",
        "ssidName": "HomeWiFi",
        "ssidPassword": "wifipass",
        "httpUsername": "admin",
        "httpPassword": "pass123",
        "WifiMode": 3,
        "ESP_MAC": "AA:BB:CC:DD:EE:FF",
        "mac_bind": 0,
        "STA_MAC": "",
    }
    base.update(overrides)
    return base


@pytest.fixture
def mock_session():
    post_mock = AsyncMock()
    post_mock.return_value.raise_for_status = MagicMock()
    post_mock.return_value.json = AsyncMock(return_value=_doc_with_network())

    session = AsyncMock()
    session.post = post_mock
    session.closed = False
    return session


class TestGetConfig:
    async def test_returns_all_network_fields(self, mock_session):
        c = Client("http://192.168.1.1", session=mock_session)
        config = await c.network.get_config()
        assert config["ssidNameAP"] == "MyAP"
        assert config["ssidPasswordAP"] == "ap123456"
        assert config["ssidName"] == "HomeWiFi"
        assert config["ssidPassword"] == "wifipass"
        assert config["httpUsername"] == "admin"
        assert config["httpPassword"] == "pass123"
        assert config["WifiMode"] == 3
        assert config["mac_bind"] == 0
        assert config["STA_MAC"] == ""


class TestSetAP:
    async def test_writes_ap_fields(self, mock_session):
        c = Client("http://192.168.1.1", session=mock_session)
        await c.network.set_ap("NewAP", "newap12345")
        call_data = mock_session.post.call_args.kwargs["data"]
        assert call_data["ssidNameAP"] == "NewAP"
        assert call_data["ssidPasswordAP"] == "newap12345"
        assert call_data["ssidPasswordAPConf"] == "newap12345"

    async def test_defaults_conf_to_password(self, mock_session):
        c = Client("http://192.168.1.1", session=mock_session)
        await c.network.set_ap("NewAP", "mypassword")
        call_data = mock_session.post.call_args.kwargs["data"]
        assert call_data["ssidPasswordAPConf"] == "mypassword"

    async def test_accepts_explicit_conf(self, mock_session):
        c = Client("http://192.168.1.1", session=mock_session)
        await c.network.set_ap("NewAP", "mypassword", "explicit")
        call_data = mock_session.post.call_args.kwargs["data"]
        assert call_data["ssidPasswordAPConf"] == "explicit"


class TestSetHTTP:
    async def test_writes_http_fields(self):
        post_mock = AsyncMock()
        post_mock.return_value.raise_for_status = MagicMock()
        post_mock.return_value.json = AsyncMock(return_value=_doc_with_network())

        session = AsyncMock()
        session.post = post_mock
        session.closed = False

        with patch("grizzl_e.client.ClientSession") as MockSession:
            MockSession.return_value = session
            c = Client("http://192.168.1.1", session=session)
            await c.network.set_http("newuser", "newpass123")
            assert session.post.call_count == 1
            call_data = session.post.call_args.kwargs["data"]
            assert call_data["httpUsername"] == "newuser"
            assert call_data["httpPassword"] == "newpass123"
            assert call_data["httpPasswordConf"] == "newpass123"

    async def test_defaults_conf_to_password(self):
        post_mock = AsyncMock()
        post_mock.return_value.raise_for_status = MagicMock()
        post_mock.return_value.json = AsyncMock(return_value=_doc_with_network())

        session = AsyncMock()
        session.post = post_mock
        session.closed = False

        with patch("grizzl_e.client.ClientSession") as MockSession:
            MockSession.return_value = session
            c = Client("http://192.168.1.1", session=session)
            await c.network.set_http("user", "mypass")
            call_data = session.post.call_args.kwargs["data"]
            assert call_data["httpPasswordConf"] == "mypass"




class TestSetSTA:
    async def test_writes_required_fields(self, mock_session):
        c = Client("http://192.168.1.1", session=mock_session)
        await c.network.set_sta("MyWiFi", "wifipass123")
        call_data = mock_session.post.call_args.kwargs["data"]
        assert call_data["ssidName"] == "MyWiFi"
        assert call_data["ssidPassword"] == "wifipass123"
        assert call_data["ssidPasswordConf"] == "wifipass123"

    async def test_writes_optional_fields(self, mock_session):
        c = Client("http://192.168.1.1", session=mock_session)
        await c.network.set_sta(
            "MyWiFi",
            "wifipass123",
            wifi_mode=2,
            mac_bind=1,
            sta_mac="AA:BB:CC:DD:EE:FF",
        )
        call_data = mock_session.post.call_args.kwargs["data"]
        assert call_data["WifiMode"] == 2
        assert call_data["mac_bind"] == 1
        assert call_data["STA_MAC"] == "AA:BB:CC:DD:EE:FF"

    async def test_defaults_conf_to_password(self, mock_session):
        c = Client("http://192.168.1.1", session=mock_session)
        await c.network.set_sta("MyWiFi", "wifipass123")
        call_data = mock_session.post.call_args.kwargs["data"]
        assert call_data["ssidPasswordConf"] == "wifipass123"


class TestNetworkProperty:
    async def test_returns_network_manager(self, mock_session):
        c = Client("http://192.168.1.1", session=mock_session)
        assert isinstance(c.network, NetworkManager)
