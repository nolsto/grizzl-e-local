from __future__ import annotations

import asyncio
import pickle
from collections import defaultdict
from collections.abc import AsyncGenerator
from functools import cached_property
from pathlib import Path
from typing import Any, Generic

import aiohttp
from aiohttp import ClientSession

from .constants import GET_PATH, INIT_PATH, SET_PATH
from .device import DependencyGraph, Device
from .document import Document, ValidationError
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
        state_file: str | Path | None = None,
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
        self._state_file = Path(state_file) if state_file else None
        self._validators = self.document_class.validators[:]

    async def __aenter__(self) -> Client:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

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

    @cached_property
    def device(self) -> Any:
        dependencies = DependencyGraph()
        return self.device_class(self, dependencies).state

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
        doc = self._document
        if doc is None:
            return True
        try:
            for validator in self._validators:
                validator(doc)
            return True
        except ValidationError:
            return False

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

    async def get(self, key: str) -> Any:
        """Async, ensures fresh document, returns a single field."""
        doc = await self.get_document()
        return getattr(doc, key)

    async def refresh(self, full: bool = False) -> None:
        """Force a refresh of the main device document from the network."""
        old_doc = self._document

        if full or self._init_data is None:
            init_data, main_data = await asyncio.gather(
                self.fetch_data(INIT_PATH),
                self.fetch_data(GET_PATH),
            )
            self._init_data = init_data
        else:
            main_data = await self.fetch_data(GET_PATH)
        data = {**self._init_data, **main_data}
        self._document = self.document_class(**data)

        if old_doc is not None:
            if diff := old_doc.diff(self._document):
                self.device.node.on_fields_changed(diff)

    async def refresh_init(self) -> None:
        """Force a refresh of the init (network config) document."""
        self._init_data = await self.fetch_data(INIT_PATH)

    async def fetch_data(self, path: str) -> dict[str, Any]:
        resp = await self.session.post(f"{self._host}{path}")
        resp.raise_for_status()
        return await resp.json()

    async def set(self, key: str, value: Any) -> None:
        """Set a single device key. No read, no validation."""
        await self.set_many(**{key: value})

    def _get_field_endpoint(self, field: str) -> str:
        field_info = self.document_class.model_fields.get(field)
        if field_info is None:
            return SET_PATH
        meta = field_info.json_schema_extra
        if meta is None:
            return SET_PATH
        return meta.get("endpoint", SET_PATH)  # type: ignore[union-attr]

    async def set_many(self, /, **data: Any) -> None:
        """Set multiple device keys in a single request. Runs validators."""
        if not data:
            return
        if self._document is not None:
            current = self._document.model_dump()
            merged = {**current, **data}
            validated = self.document_class(**merged)
            for validator in self._validators:
                if validator.fields & data.keys():
                    validator(validated)
        by_endpoint: dict[str, dict[str, Any]] = defaultdict(dict)
        for key, value in data.items():
            endpoint = self._get_field_endpoint(key)
            by_endpoint[endpoint][key] = value
        await asyncio.gather(
            *[self.session.post(f"{self._host}{endpoint}", data=chunk)
              for endpoint, chunk in by_endpoint.items()]
        )
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

    def save_state(self, key: str, value: Any) -> None:
        """Persist a value to the state file.

        Raises RuntimeError if no state_file was provided.
        """
        if self._state_file is None:
            raise RuntimeError("No state_file configured")
        data: dict[str, Any] = {}
        if self._state_file.exists():
            with open(self._state_file, "rb") as f:
                data = pickle.load(f)
        data[key] = value
        with open(self._state_file, "wb") as f:
            pickle.dump(data, f)

    def load_state(self, key: str) -> Any:
        """Load a value from the state file."""
        if self._state_file is None:
            raise RuntimeError("No state_file configured")
        if not self._state_file.exists():
            raise KeyError(key)
        with open(self._state_file, "rb") as f:
            data = pickle.load(f)
        return data[key]

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
