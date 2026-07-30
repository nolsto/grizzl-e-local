from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Generic

import aiohttp
from aiohttp import ClientSession
from aiorwlock import RWLock

from .constants import Endpoint
from .context import transaction_batch
from .device import DependencyGraph, Device
from .document import Document
from .types import DocT, DeviceT


class Client(Generic[DocT, DeviceT]):
    """Async client for the Grizzl-E EVSE device.

    Usage::

        async with Client("http://192.168.20.101") as c:
            doc = await c.get_document()
            print(doc.state)
            await c.set("evseEnabled", True)

            async for doc in c.watch(1.0):
                print(doc.currentSet)
    """

    document_class: type[DocT] = Document  # type: ignore[assignment]
    device_class: type[DeviceT] = Device  # type: ignore[assignment]

    def __init__(
        self,
        host: str,
        session: ClientSession | None = None,
        username: str = "",
        password: str = "",
    ) -> None:
        self._host = host.rstrip("/")
        self._session: ClientSession | None = session
        self._username = username
        self._password = password
        self._document: DocT | None = None
        self._expired_document: DocT | None = None
        self._init_data: dict[str, Any] | None = None
        self._locks = {e: RWLock() for e in Endpoint}
        self._device: DeviceT = self.device_class(self, DependencyGraph())

    async def __aenter__(self) -> Client:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    @asynccontextmanager
    async def transaction(self, refresh=False):
        batch: dict[str, object] = {}
        token = transaction_batch.set(batch)

        try:
            yield batch
        finally:
            transaction_batch.reset(token)
            if batch:
                await self.set_many(**batch)
                if refresh:
                    await self.refresh()

    @property
    def session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            headers = {}
            if self._username:
                headers["Authorization"] = aiohttp.encode_basic_auth(
                    self._username, self._password,
                )
            self._session = ClientSession(headers=headers if headers else None)
        return self._session

    @property
    def device(self) -> Any:
        return self._device.state

    @property
    def document(self) -> DocT:
        """The cached or expired document"""
        if self._document is None:
            if self._expired_document is None:
                raise RuntimeError(
                    "Document not yet fetched. Call refresh() or get_document() first.",
                )
            return self._expired_document
        return self._document

    @property
    def is_valid(self) -> bool:
        return self.document.is_valid()

    def _expire_document(self) -> None:
        if self._document is None:
            return
        self._expired_document = self._document
        self._document = None

    async def get_document(self) -> DocT:
        """Fetch the full device document. Uses a cached copy if available."""
        if self._document is None:
            await self.refresh()
        assert self._document is not None
        return self._document

    get_data = get_document

    async def get(self, key: str) -> object:
        """Async, ensures fresh document, returns a single field."""
        doc = await self.get_document()
        return getattr(doc, key)

    async def refresh(self, full: bool = False) -> None:
        """Force a refresh of the main device document from the network."""
        old_doc = self._document

        if full or self._init_data is None:
            init_data, main_data = await asyncio.gather(
                self.fetch_data(Endpoint.INIT),
                self.fetch_data(Endpoint.GET),
            )
            self._init_data = init_data
        else:
            main_data = await self.fetch_data(Endpoint.GET)
        data = {**self._init_data, **main_data}
        self._document = self.document_class(**data)

        if old_doc is not None:
            if diff := old_doc.diff(self._document):
                for component in self._device.dependencies:
                    if fields := component.fields & diff:
                        component.on_fields_changed(fields)

    async def refresh_init(self) -> None:
        """Force a refresh of the init (network config) document."""
        self._init_data = await self.fetch_data(Endpoint.INIT)

    async def fetch_data(self, endpoint: Endpoint) -> dict[str, object]:
        async with self._locks[endpoint].reader_lock:  # type: ignore[bad-context-manager]
            resp = await self.session.post(f"{self._host}{endpoint.value}")
        resp.raise_for_status()
        return await resp.json()

    async def post_data(self, endpoint: Endpoint, data: dict[str, object]) -> None:
        async with self._locks[endpoint].writer_lock:  # type: ignore[bad-context-manager]
            await self.session.post(f"{self._host}{endpoint.value}", data=data)

    async def set(self, key: str, value: object) -> None:
        """Set a single device key. No read, no validation."""
        await self.set_many(**{key: value})

    async def set_many(self, /, **data: object) -> None:
        """Set multiple device keys in a single request. Validates independently."""
        if not data:
            return
        try:
            batch = transaction_batch.get()
        except LookupError:
            pass
        else:
            batch.update(data)
            return
        doc = self.document_class()
        if self._document is not None:
            doc.update(self._document)
        doc.update(data)
        serialized = doc.serialize()
        doc.run_validators()
        by_endpoint: dict[Endpoint, dict[str, object]] = defaultdict(dict)
        for key, value in data.items():
            endpoint = doc.get_endpoint(key)
            serialized_value = serialized.get(key, value)
            by_endpoint[endpoint][key] = serialized_value
        await asyncio.gather(*(self.post_data(ep, payload) for ep, payload in by_endpoint.items()))
        self._expire_document()
        if "httpUsername" in data or "httpPassword" in data:
            await self.close()

    async def watch(self, interval: float = 1.0) -> AsyncGenerator[DocT, None]:
        """Poll the device at the given interval, yielding the document each time.

        The caller is responsible for breaking out of the loop.
        """
        while True:
            yield await self.get_document()
            await asyncio.sleep(interval)

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
