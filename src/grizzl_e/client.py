from __future__ import annotations

import asyncio
import pickle
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, overload

from aiohttp import ClientSession, encode_basic_auth

from . import managers
from .document import Document

_GET_PATH = "/main"
_SET_PATH = "/pageEvent"
_INIT_PATH = "/init"


class _LazyManager:
    """Descriptor for lazy-initializing manager instances."""

    def __init__(self, cls: type) -> None:
        self._cls = cls

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr = f"_{name}"

    @overload
    def __get__(self, obj: None, objtype: None) -> _LazyManager: ...

    @overload
    def __get__(self, obj: Client, objtype: type) -> object: ...

    def __get__(self, obj: Client | None, objtype: type | None = None):
        if obj is None:
            return self
        mgr = getattr(obj, self._attr, None)
        if mgr is None:
            mgr = self._cls(obj)
            setattr(obj, self._attr, mgr)
        return mgr  # type: ignore[return-value]


class Client:
    """Async client for the Grizzl-E EVSE device.

    Usage::

        async with Client("http://192.168.20.101") as c:
            doc = await c.get_document()
            print(doc.state)
            await c.set("evseEnabled", 1)

            async for doc in c.watch(1.0):
                print(doc.currentSet)
    """

    def __init__(
        self,
        host: str,
        session: ClientSession | None = None,
        state_file: str | Path | None = None,
        username: str = "",
        password: str = "",
    ) -> None:
        self._host = host.rstrip("/")
        self._session = session
        self._username = username
        self._password = password
        self._doc_cache: Document | None = None
        self._init_data: dict[str, Any] | None = None
        self._state_file = Path(state_file) if state_file else None
        self._tariffs: managers.TariffManager | None = None
        self._limits: managers.LimitsManager | None = None
        self._time: managers.TimeManager | None = None
        self._network: managers.NetworkManager | None = None

    async def _get_session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            headers = {}
            if self._username:
                headers["Authorization"] = encode_basic_auth(self._username, self._password)
            self._session = ClientSession(headers=headers if headers else None)
        return self._session

    async def _invalidate_session(self) -> None:
        """Close the current session so the next request creates a new one with auth."""
        await self.close()
        self._session = None

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> Client:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def get_document(self) -> Document:
        """Fetch the full device document. Uses a cached copy if available."""
        if self._doc_cache is None:
            await self.refresh()
        assert self._doc_cache is not None
        return self._doc_cache

    async def refresh(self) -> None:
        """Force a refresh of the main device document from the network."""
        session = await self._get_session()
        resp = await session.post(f"{self._host}{_GET_PATH}")
        resp.raise_for_status()
        main_data = await resp.json()
        data = self._merge_init(main_data)
        self._doc_cache = Document(**data)

    def _merge_init(self, main_data: dict[str, Any]) -> dict[str, Any]:
        """Merge cached init data into main data, main takes precedence."""
        if self._init_data is None:
            return main_data
        return {**self._init_data, **main_data}

    async def init(self) -> Document:
        """Fetch both main and init documents, returning a merged Document."""
        session = await self._get_session()

        resp_main = await session.post(f"{self._host}{_GET_PATH}")
        resp_main.raise_for_status()
        main_data = await resp_main.json()

        resp_init = await session.post(f"{self._host}{_INIT_PATH}")
        resp_init.raise_for_status()
        init_data = await resp_init.json()

        # Merge: init fields first, main fields override overlapping keys
        merged = {**init_data, **main_data}
        self._init_data = init_data
        self._doc_cache = Document(**merged)
        return self._doc_cache

    async def refresh_init(self) -> None:
        """Force a refresh of the init (network config) document."""
        session = await self._get_session()
        resp = await session.post(f"{self._host}{_INIT_PATH}")
        resp.raise_for_status()
        self._init_data = await resp.json()

    async def set(self, key: str, value: Any) -> None:
        """Set a single device key. No read, no validation."""
        await self.set_many(**{key: value})

    async def set_many(self, /, **data: Any) -> None:
        """Set multiple device keys in a single request. No read, no validation."""
        session = await self._get_session()
        await session.post(f"{self._host}{_SET_PATH}", data=data)
        # Invalidate cache since we modified state
        self._doc_cache = None
        # Device reboots when HTTP credentials change — invalidate session
        if "httpUsername" in data or "httpPassword" in data:
            await self._invalidate_session()

    async def watch(self, interval: float = 1.0) -> AsyncGenerator[Document, None]:
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
        data = {}
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

    @property
    def is_valid(self) -> bool:
        """Check if the current document satisfies all invariants."""
        doc = self._doc_cache
        if doc is None:
            return True  # nothing to validate

        if doc.currentSet > doc.curDesign:
            return False

        # AP WiFi password: empty or >= 8 chars
        pwd = doc.ssidPasswordAP
        if pwd and len(pwd) < 8:
            return False

        # STA WiFi password: empty or >= 8 chars
        pwd = doc.ssidPassword
        if pwd and len(pwd) < 8:
            return False

        # HTTP: can't have password without username
        if doc.httpUsername == "" and doc.httpPassword != "":
            return False

        return True

    tariffs = _LazyManager(managers.TariffManager)
    limits = _LazyManager(managers.LimitsManager)
    time = _LazyManager(managers.TimeManager)
    network = _LazyManager(managers.NetworkManager)
