from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..managers import Manager

if TYPE_CHECKING:
    from ..client import Client


@dataclass(frozen=True)
class LimitState:
    time: int
    energy: int
    money: int
    suspended: bool


class LimitsManager(Manager):
    """Manages limit state, including suspend/resume with persistence."""

    _STATE_KEY = "limits"

    async def get_state(self) -> LimitState:
        """Read the current limit state from the device."""
        doc = await self._client.get_document()
        return LimitState(
            time=doc.timeLimit,
            energy=doc.energyLimit,
            money=doc.moneyLimit,
            suspended=bool(doc.suspendLimits),
        )

    async def suspend(self) -> None:
        """Save current limits, then suspend all limits on the device."""
        state = await self.get_state()
        self._client.save_state(self._STATE_KEY, state)
        await self.set(
            suspendLimits=1,
            timeLimit=0,
            energyLimit=0,
            moneyLimit=0,
        )

    async def resume(self) -> None:
        """Restore previously suspended limits on the device."""
        saved = self._client.load_state(self._STATE_KEY)
        if not isinstance(saved, LimitState):
            raise RuntimeError("Saved limit state is corrupted or missing")
        await self.set(
            suspendLimits=0,
            timeLimit=saved.time,
            energyLimit=saved.energy,
            moneyLimit=saved.money,
        )
