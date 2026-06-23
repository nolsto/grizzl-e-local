from unittest.mock import AsyncMock, MagicMock, patch, patch

import pytest

from grizzl_e.client import Client
from grizzl_e.document import Document


def _main_doc_data():
    """Data returned by /main — does NOT include init fields."""
    return {
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
        "suspendErrors": 0, "suspendLimits": 0, "oneCharge": 0,
        "delayedLimit": 0, "timeLimit": 0, "energyLimit": 0,
        "moneyLimit": 0, "sh1Enabled": 1, "sh1Start": 0, "sh1Stop": 360,
        "sh1CurrentEnable": 0, "sh1CurrentValue": 12,
        "sh1EnergyEnable": 0, "sh1EnergyValue": 3, "sh2Enabled": 0,
        "sh2Start": 0, "sh2Stop": 0, "sh2CurrentEnable": 0,
        "sh2CurrentValue": 12, "sh2EnergyEnable": 0, "sh2EnergyValue": 0,
        "totalEnergy": 0, "sessionTime": 0, "sessionEnergy": 0,
        "sessionMoney": 0, "sessionStarted": 0, "IEM1": 0, "IEM2": 0,
        "IEM1_money": 0, "IEM2_money": 0, "curMeas1": 0, "curMeas2": 0,
        "curMeas3": 0, "voltMeas1": 241, "voltMeas2": 0, "voltMeas3": 0,
        "powerMeas": 0, "temperature1": 34, "temperature2": 34,
        "leakValue": 15, "leakValueH": 13, "vBat": 2.86, "adapter": 255,
        "scanComplete": 0, "ocppconnected": 0, "ocppEnabled": 0,
        "ocppOfflineAva": 1, "STA_IP_Addres": "192.168.1.1", "RSSI": -62,
        "logReady": 1, "lang": 1,
    }


def _init_doc_data():
    """Data returned by /init — init-specific network config."""
    return {
        "ssidNameAP": "GRU-L0000310350", "ssidPasswordAP": "",
        "ssidName": "The Coop", "ssidPassword": "",
        "httpUsername": "", "httpPassword": "",
        "WifiMode": 3, "ESP_MAC": "B4:8A:0A:8A:4E:10",
        "mac_bind": 0, "STA_MAC": "",
    }


def _minimal_doc_data():
    """Full document data for tests that don't distinguish endpoints."""
    return {**_main_doc_data(), **_init_doc_data()}


@pytest.fixture
def mock_session():
    post_mock = AsyncMock()
    post_mock.return_value.raise_for_status = MagicMock()
    post_mock.return_value.json = AsyncMock(return_value=_minimal_doc_data())

    session = AsyncMock()
    session.post = post_mock
    session.closed = False
    return session


@pytest.fixture
def client(mock_session):
    return Client("http://192.168.1.1", session=mock_session)


class TestGetDocument:
    async def test_fetches_from_device(self, client, mock_session):
        doc = await client.get_document()
        assert isinstance(doc, Document)
        assert doc.serialNum == "test"
        mock_session.post.assert_called_once_with("http://192.168.1.1/main")

    async def test_caches_result(self, client, mock_session):
        await client.get_document()
        await client.get_document()
        assert mock_session.post.call_count == 1

    async def test_refresh_invalidates_cache(self, client, mock_session):
        await client.get_document()
        await client.refresh()
        assert mock_session.post.call_count == 2

    async def test_host_trailing_slash_stripped(self):
        with patch("grizzl_e.client.ClientSession") as MockSession:
            mock = AsyncMock()
            mock.post = AsyncMock()
            mock.post.return_value.raise_for_status = MagicMock()
            mock.post.return_value.json = AsyncMock(return_value=_minimal_doc_data())
            mock.closed = False
            MockSession.return_value = mock

            c = Client("http://192.168.1.1/")
            await c.get_document()
            mock.post.assert_called_once_with("http://192.168.1.1/main")


class TestSet:
    async def test_sets_single_key(self, client, mock_session):
        await client.set("evseEnabled", 1)
        mock_session.post.assert_called_with(
            "http://192.168.1.1/pageEvent", data={"evseEnabled": 1}
        )

    async def test_set_invalidates_cache(self, client, mock_session):
        await client.get_document()
        await client.set("evseEnabled", 1)
        assert client._doc_cache is None

    async def test_set_with_string_value(self, client, mock_session):
        await client.set("lang", "en")
        mock_session.post.assert_called_with(
            "http://192.168.1.1/pageEvent", data={"lang": "en"}
        )


class TestWatch:
    async def test_yields_documents(self, client, mock_session):
        results = []
        i = 0
        async for doc in client.watch(interval=0.01):
            results.append(doc)
            i += 1
            if i >= 3:
                break
        assert len(results) == 3
        assert all(isinstance(d, Document) for d in results)

    async def test_uses_cached_document(self, client, mock_session):
        count = 0
        async for doc in client.watch(interval=0.01):
            count += 1
            if count >= 2:
                break
        # First iteration fetches, subsequent use cache
        assert mock_session.post.call_count == 1


class TestIsValid:
    async def test_valid_current(self, client, mock_session):
        # curDesign=40, currentSet=32 → valid
        assert client.is_valid is True

    async def test_invalid_current(self, client, mock_session):
        mock_session.post.return_value.json = AsyncMock(
            return_value={**_minimal_doc_data(), "currentSet": 50, "curDesign": 40}
        )
        doc = await client.get_document()
        assert doc.currentSet == 50
        assert doc.curDesign == 40
        assert client.is_valid is False

    async def test_valid_ap_password_empty(self, client, mock_session):
        assert client.is_valid is True

    async def test_valid_ap_password_long_enough(self, client, mock_session):
        mock_session.post.return_value.json = AsyncMock(
            return_value={**_minimal_doc_data(), "ssidPasswordAP": "12345678"}
        )
        await client.get_document()
        assert client.is_valid is True

    async def test_invalid_ap_password_too_short(self, client, mock_session):
        mock_session.post.return_value.json = AsyncMock(
            return_value={**_minimal_doc_data(), "ssidPasswordAP": "1234567"}
        )
        await client.get_document()
        assert client.is_valid is False

    async def test_valid_sta_password_empty(self, client, mock_session):
        assert client.is_valid is True

    async def test_valid_sta_password_long_enough(self, client, mock_session):
        mock_session.post.return_value.json = AsyncMock(
            return_value={**_minimal_doc_data(), "ssidPassword": "12345678"}
        )
        await client.get_document()
        assert client.is_valid is True

    async def test_invalid_sta_password_too_short(self, client, mock_session):
        mock_session.post.return_value.json = AsyncMock(
            return_value={**_minimal_doc_data(), "ssidPassword": "1234567"}
        )
        await client.get_document()
        assert client.is_valid is False

    async def test_valid_http_no_password(self, client, mock_session):
        assert client.is_valid is True

    async def test_valid_http_with_username_and_password(self, client, mock_session):
        mock_session.post.return_value.json = AsyncMock(
            return_value={
                **_minimal_doc_data(),
                "httpUsername": "admin",
                "httpPassword": "secret",
            }
        )
        await client.get_document()
        assert client.is_valid is True

    async def test_invalid_http_password_without_username(self, client, mock_session):
        mock_session.post.return_value.json = AsyncMock(
            return_value={
                **_minimal_doc_data(),
                "httpUsername": "",
                "httpPassword": "secret",
            }
        )
        await client.get_document()
        assert client.is_valid is False


class TestInit:
    async def test_init_fetches_both_endpoints(self, mock_session):
        mock_session.post.side_effect = [
            MagicMock(**{"raise_for_status": MagicMock(), "json": AsyncMock(return_value=_main_doc_data())}),
            MagicMock(**{"raise_for_status": MagicMock(), "json": AsyncMock(return_value=_init_doc_data())}),
        ]
        doc = await Client("http://192.168.1.1", session=mock_session).init()
        assert doc.serialNum == "test"
        assert doc.ssidName == "The Coop"
        assert doc.WifiMode == 3
        assert mock_session.post.call_count == 2

    async def test_refresh_does_not_fetch_init(self, client, mock_session):
        await client.init()
        mock_session.post.reset_mock()
        mock_session.post.return_value.raise_for_status = MagicMock()
        mock_session.post.return_value.json = AsyncMock(return_value=_main_doc_data())
        await client.refresh()
        # Only /main should be called, not /init
        calls = [c[0] for c in mock_session.post.call_args_list]
        assert calls == [("http://192.168.1.1/main",)]

    async def test_refresh_init_only(self, client, mock_session):
        await client.init()
        mock_session.post.reset_mock()
        new_init = {
            "ssidNameAP": "NewAP", "ssidPasswordAP": "",
            "ssidName": "NewSSID", "ssidPassword": "",
            "httpUsername": "", "httpPassword": "",
            "WifiMode": 1, "ESP_MAC": "AA:BB:CC:DD:EE:FF",
            "mac_bind": 1, "STA_MAC": "11:22:33:44:55:66",
        }
        mock_session.post.return_value.raise_for_status = MagicMock()
        mock_session.post.return_value.json = AsyncMock(return_value=new_init)
        await client.refresh_init()
        assert client._init_data["ssidName"] == "NewSSID"
        assert client._init_data["WifiMode"] == 1

    async def test_refresh_after_refresh_init_uses_new_init_data(self, mock_session):
        c = Client("http://192.168.1.1", session=mock_session)
        # Set up side_effect for sequential calls
        new_init = {
            "ssidNameAP": "NewAP", "ssidPasswordAP": "",
            "ssidName": "NewSSID", "ssidPassword": "",
            "httpUsername": "", "httpPassword": "",
            "WifiMode": 1, "ESP_MAC": "AA:BB:CC:DD:EE:FF",
            "mac_bind": 1, "STA_MAC": "11:22:33:44:55:66",
        }
        mock_session.post.side_effect = [
            MagicMock(**{"raise_for_status": MagicMock(), "json": AsyncMock(return_value=_main_doc_data())}),
            MagicMock(**{"raise_for_status": MagicMock(), "json": AsyncMock(return_value=new_init)}),
            MagicMock(**{"raise_for_status": MagicMock(), "json": AsyncMock(return_value=new_init)}),
            MagicMock(**{"raise_for_status": MagicMock(), "json": AsyncMock(return_value=_main_doc_data())}),
        ]
        # Initial fetch of both endpoints
        await c.init()
        assert c._init_data["ssidNameAP"] == "NewAP"
        # Refresh init
        await c.refresh_init()
        assert c._init_data["ssidNameAP"] == "NewAP"
        # Refresh main — should merge with updated init data
        await c.refresh()
        assert c._doc_cache is not None
        assert c._doc_cache.ssidNameAP == "NewAP"


class TestHTTPAuth:
    async def test_reconnects_on_http_username_change(self):
        post_mock = AsyncMock()
        post_mock.return_value.raise_for_status = MagicMock()
        post_mock.return_value.json = AsyncMock(return_value=_minimal_doc_data())

        session = AsyncMock()
        session.post = post_mock
        session.closed = False

        with patch("grizzl_e.client.ClientSession") as MockSession:
            MockSession.return_value = session
            c = Client("http://192.168.1.1", session=session, username="newuser", password="newpass")
            await c.set("httpUsername", "newuser")
            assert c._session is None
            await c.get_document()
            # Session was recreated with auth header
            MockSession.assert_called()
            call_kwargs = MockSession.call_args
            assert call_kwargs[1]["headers"]["Authorization"] is not None

    async def test_reconnects_on_http_password_change(self):
        post_mock = AsyncMock()
        post_mock.return_value.raise_for_status = MagicMock()
        post_mock.return_value.json = AsyncMock(return_value=_minimal_doc_data())

        session = AsyncMock()
        session.post = post_mock
        session.closed = False

        with patch("grizzl_e.client.ClientSession") as MockSession:
            MockSession.return_value = session
            c = Client("http://192.168.1.1", session=session, username="user", password="newpass")
            await c.set("httpPassword", "newpass")
            assert c._session is None
            await c.get_document()
            assert c._session is not None
            MockSession.assert_called()
            call_kwargs = MockSession.call_args
            assert call_kwargs[1]["headers"]["Authorization"] is not None

    async def test_no_reconnect_on_other_keys(self, mock_session):
        c = Client("http://192.168.1.1", session=mock_session)
        mock_session.post.return_value.raise_for_status = MagicMock()
        mock_session.post.return_value.json = AsyncMock(return_value=_minimal_doc_data())
        await c.set("evseEnabled", 1)
        assert c._session is mock_session


class TestLifecycle:
    async def test_context_manager(self, mock_session):
        async with Client("http://192.168.1.1", session=mock_session) as c:
            await c.get_document()
        mock_session.close.assert_called_once()

    async def test_tariffs_property(self, client):
        from grizzl_e.managers.tariffs import TariffManager
        assert isinstance(client.tariffs, TariffManager)
