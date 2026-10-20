from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grizzl_e_local.client import Client
from grizzl_e_local.client.versions import Version_01
from grizzl_e_local.document.base import BaseDocument
from grizzl_e_local.document.validation import ValidationError
from grizzl_e_local.document.versions import HttpAuthValidator


class _ClientWithDoc(Client):
    def __init__(self, *args, document_class=None, **kwargs):
        super().__init__(*args, **kwargs)
        if document_class is not None:
            self.document_class = document_class


class TestGetDocument:
    async def test_fetches_from_device(self, session):

        class Doc(BaseDocument):
            pass

        client = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await client.get_document()
        calls = [c[0][0] for c in client.session.post.call_args_list]
        assert "http://192.168.1.1/init" in calls
        assert "http://192.168.1.1/main" in calls

    async def test_caches_result(self, session):

        class Doc(BaseDocument):
            pass

        client = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await client.get_document()
        call_count_after_first_fetch = client.session.post.call_count
        await client.get_document()
        await client.get_document()
        assert client.session.post.call_count == call_count_after_first_fetch

    async def test_refresh_invalidates_cache(self, session):

        class Doc(BaseDocument):
            pass

        client = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await client.get_document()
        call_count_after_first_fetch = client.session.post.call_count
        await client.refresh()
        assert client.session.post.call_count == call_count_after_first_fetch + 1

    async def test_host_trailing_slash_stripped(self, session):
        class Doc(BaseDocument):
            pass

        c = _ClientWithDoc("http://192.168.1.1/", session=session, document_class=Doc)
        await c.refresh()
        calls = [c[0][0] for c in session.post.call_args_list]
        assert "http://192.168.1.1/init" in calls
        assert "http://192.168.1.1/main" in calls


class TestSet:
    async def test_sets_single_key(self, session):

        class Doc(BaseDocument):
            evseEnabled: int

        client = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await client.set("evseEnabled", 1)
        session.post.assert_called_with(
            "http://192.168.1.1/pageEvent", data={"evseEnabled": 1}
        )

    async def test_set_invalidates_cache(self, session):

        class Doc(BaseDocument):
            evseEnabled: int

        client = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await client.get_document()
        await client.set("evseEnabled", 1)
        assert client._document is None

    async def test_set_with_string_value(self, session):

        class Doc(BaseDocument):
            ssidName: str

        client = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await client.set("ssidName", "MyNetwork")
        session.post.assert_called_with(
            "http://192.168.1.1/pageEvent", data={"ssidName": "MyNetwork"}
        )


class TestWatch:
    async def test_yields_documents(self, session):

        class Doc(BaseDocument):
            pass

        client = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await client.get_document()
        results = []
        i = 0
        async for doc in client.watch(interval=0.01):
            results.append(doc)
            i += 1
            if i >= 3:
                break
        assert len(results) == 3

    async def test_uses_cached_document(self, session):

        class Doc(BaseDocument):
            pass

        client = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await client.get_document()
        call_count_after_first_fetch = session.post.call_count
        count = 0
        async for doc in client.watch(interval=0.01):
            count += 1
            if count >= 2:
                break
        assert session.post.call_count == call_count_after_first_fetch


class TestInit:
    async def test_init_fetches_both_endpoints(self, session):
        session.post.return_value.raise_for_status = MagicMock()

        class Doc(BaseDocument):
            serialNum: str
            ssidName: str
            WifiMode: int

        session.post.side_effect = [
            MagicMock(raise_for_status=MagicMock(), json=AsyncMock(return_value={"serialNum": "test"})),
            MagicMock(raise_for_status=MagicMock(), json=AsyncMock(return_value={"WifiMode": 3})),
        ]

        c = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await c.refresh()
        assert c.document.serialNum == "test"
        assert c.document.WifiMode == 3
        assert session.post.call_count == 2

    async def test_refresh_does_not_fetch_init(self, session):

        class Doc(BaseDocument):
            pass

        client = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await client.refresh()
        session.post.reset_mock()
        session.post.return_value.json = AsyncMock(return_value={})
        await client.refresh()
        calls = [c[0] for c in session.post.call_args_list]
        assert calls == [("http://192.168.1.1/main",)]

    async def test_refresh_full_fetches_both_endpoints(self, session):

        class Doc(BaseDocument):
            pass

        client = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await client.refresh()
        session.post.reset_mock()
        session.post.return_value.raise_for_status = MagicMock()

        await client.refresh(full=True)

        calls = [c[0][0] for c in session.post.call_args_list]
        assert "http://192.168.1.1/init" in calls
        assert "http://192.168.1.1/main" in calls

    async def test_refresh_after_refresh_init_uses_new_init_data(self, session):
        session.post.return_value.raise_for_status = MagicMock()
        session.post.side_effect = [
            MagicMock(raise_for_status=MagicMock(), json=AsyncMock(return_value={"ssidNameAP": "NewAP"})),
            MagicMock(raise_for_status=MagicMock(), json=AsyncMock(return_value={})),
            MagicMock(raise_for_status=MagicMock(), json=AsyncMock(return_value={"ssidNameAP": "NewAP"})),
            MagicMock(raise_for_status=MagicMock(), json=AsyncMock(return_value={})),
        ]

        class Doc(BaseDocument):
            ssidNameAP: str

        c = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await c.refresh()
        assert c._init_data["ssidNameAP"] == "NewAP"
        await c.refresh_init()
        assert c._init_data["ssidNameAP"] == "NewAP"
        await c.refresh()
        assert c._document is not None
        assert c._document.ssidNameAP == "NewAP"


class TestHTTPAuth:
    async def test_reconnects_on_http_username_change(self, session):
        session.post.return_value.raise_for_status = MagicMock()
        session.post.return_value.json = AsyncMock(return_value={})

        with patch("grizzl_e_local.client.base.ClientSession") as MockSession:
            MockSession.return_value = session
            class Doc(BaseDocument):
                httpUsername: str
                evseEnabled: int

            c = _ClientWithDoc(
                "http://192.168.1.1", session=session, document_class=Doc,
                username="newuser", password="newpass"
            )
            await c.refresh()
            await c.set("httpUsername", "newuser")
            assert c._session is None
            await c.get_document()
            MockSession.assert_called()
            call_kwargs = MockSession.call_args
            assert call_kwargs[1]["headers"]["Authorization"] is not None

    async def test_reconnects_on_http_password_change(self, session):
        session.post.return_value.raise_for_status = MagicMock()
        session.post.return_value.json = AsyncMock(return_value={})


        with patch("grizzl_e_local.client.base.ClientSession") as MockSession:
            MockSession.return_value = session
            class Doc(BaseDocument):
                httpUsername: str
                httpPassword: str

            c = _ClientWithDoc(
                "http://192.168.1.1", session=session, document_class=Doc,
                username="user", password="newpass"
            )
            await c.refresh()
            await c.set_many(httpUsername="user", httpPassword="newpass")
            assert c._session is None
            await c.get_document()
            assert c._session is not None
            MockSession.assert_called()
            call_kwargs = MockSession.call_args
            assert call_kwargs[1]["headers"]["Authorization"] is not None

    async def test_no_reconnect_on_other_keys(self, session):
        session.post.return_value.raise_for_status = MagicMock()
        session.post.return_value.json = AsyncMock(return_value={})


        class Doc(BaseDocument):
            evseEnabled: int

        c = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await c.set("evseEnabled", 1)
        assert c._session is session


class TestLifecycle:
    async def test_context_manager(self, session):
        session.post.return_value.raise_for_status = MagicMock()
        session.post.return_value.json = AsyncMock(return_value={})

        class Doc(BaseDocument):
            pass

        async with _ClientWithDoc(
            "http://192.168.1.1", session=session, document_class=Doc
        ) as c:
            await c.get_document()
        session.close.assert_called_once()


class TestValidationMergedState:
    async def test_set_many_merges_existing_document_before_validating(self, session):
        """set_many merges _document into validation doc before running validators."""

        class _ValidatedDoc(BaseDocument):
            httpUsername: str
            httpPassword: str
            validators = [HttpAuthValidator()]

        doc = _ValidatedDoc()
        doc["httpUsername"] = ""  # existing empty username from device
        doc["httpPassword"] = ""

        c = _ClientWithDoc("http://192.168.1.1", session=session, document_class=_ValidatedDoc)
        # Manually set the cached document (simulating get_document result)
        c._document = doc

        with pytest.raises(ValidationError, match="httpUsername required"):
            await c.set_many(httpPassword="newpassword")


class TestTransactionBatching:
    async def test_set_many_accumulates_in_transaction(self, session):
        class Doc(BaseDocument):
            ssidNameAP: str
            httpUsername: str

        # Override json return for this test's needs
        session.post.return_value.json = AsyncMock(return_value={"ssidNameAP": "existingSSID"})

        c = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await c.get_document()

        post_count_before = session.post.call_count

        async with c.transaction():
            await c.set_many(ssidNameAP="newSSID")
            await c.set_many(httpUsername="admin")

        # One POST for the batch flush on exit
        assert session.post.call_count == post_count_before + 1
        call_args = session.post.call_args_list[-1]
        data = call_args[1].get("data") or call_args[1].get("json", {})
        assert data["ssidNameAP"] == "newSSID"
        assert data["httpUsername"] == "admin"

    async def test_transaction_flushes_once_on_exit(self, session):
        class Doc(BaseDocument):
            ssidNameAP: str
            httpPassword: str
            currentSet: int

        c = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await c.get_document()

        post_count_before = session.post.call_count

        async with c.transaction():
            await c.set_many(ssidNameAP="ssid1")
            await c.set_many(httpPassword="secret123")
            await c.set_many(currentSet=50)

        # Only one POST for all accumulated data on exit
        assert session.post.call_count == post_count_before + 1

    async def test_transaction_empty_does_not_post(self, session):
        class Doc(BaseDocument):
            pass

        c = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)
        await c.get_document()

        post_count_before = session.post.call_count

        async with c.transaction():
            pass  # no writes

        assert session.post.call_count == post_count_before

    async def test_set_many_outside_transaction_posts_immediately(self, session):
        class Doc(BaseDocument):
            ssidNameAP: str

        c = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)

        await c.set_many(ssidNameAP="newSSID")

        assert session.post.call_count == 1

    async def test_set_many_resolves_lazy_values(self, session):
        class Doc(BaseDocument):
            systemTime: int
            timeZone: int

        calls = [0]

        def make_epoch():
            calls[0] += 1
            return 1750000000 + calls[0]

        c = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)

        await c.set_many(systemTime=make_epoch, timeZone=lambda: -5)

        call_args = session.post.call_args_list[-1]
        data = call_args[1].get("data") or call_args[1].get("json", {})
        assert data["systemTime"] == 1750000001
        assert data["timeZone"] == -5
        # Resolved exactly once at flush, not lazily on every access.
        assert calls[0] == 1

    async def test_transaction_flush_resolves_lazy_values(self, session):
        class Doc(BaseDocument):
            systemTime: int

        c = _ClientWithDoc("http://192.168.1.1", session=session, document_class=Doc)

        async with c.transaction():
            await c.set_many(systemTime=lambda: 1750000123)

        call_args = session.post.call_args_list[-1]
        data = call_args[1].get("data") or call_args[1].get("json", {})
        assert data["systemTime"] == 1750000123


class TestCrossComponentExceptionState:
    """Our own write path refuses to lower currentSet below an active schedule limit,
    but the firmware can hold such a state when configured externally; refresh must
    flag the dependent component rather than raise."""

    async def test_refresh_flags_schedule_limit_on_breach(self, session):
        main_fetches = 0

        async def post(url: str, *args: object, **kwargs: object) -> MagicMock:
            nonlocal main_fetches
            response = MagicMock()
            if "init" in url:
                data = {}
            else:
                main_fetches += 1
                # Second fetch simulates currentSet being lowered on the device itself.
                data = (
                    {"currentSet": 32, "sh1CurrentValue": 30}
                    if main_fetches == 1
                    else {"currentSet": 27, "sh1CurrentValue": 30}
                )
            response.json = AsyncMock(return_value=data)
            response.raise_for_status = MagicMock()
            return response

        session.post = post
        client = Version_01("http://192.168.1.1", session=session)
        await client.get_document()

        node = client.device.schedules[0].current_limit._node  # type: ignore[reportAttributeAccessIssue]
        assert not node.in_exception_state

        await client.refresh()
        assert node.in_exception_state
        assert "greater than device limit" in str(node.exceptions[0])
