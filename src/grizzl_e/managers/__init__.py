from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import Client


class Manager:
    """Base class for all device managers."""

    def __init__(self, client: Client) -> None:
        self._client = client

    @property
    def client(self) -> Client:
        return self._client

    async def get(self) -> dict[str, Any]:
        """Read the current state from the device."""
        doc = await self._client.get_document()
        return doc.model_dump()

    async def set(self, /, **data: Any) -> None:
        """Write multiple keys in a single request."""
        await self._client.set_many(**data)


from .limits import LimitsManager
from .network import NetworkManager
from .tariffs import TariffManager
from .time import TimeManager

__all__ = ["LimitsManager", "NetworkManager", "TariffManager", "TimeManager", "Manager"]
