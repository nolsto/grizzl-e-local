from __future__ import annotations

from dataclasses import dataclass

from .base import Manager
from ..document import Document


@dataclass(frozen=True)
class LimitState:
    time: int
    energy: int
    money: int
    suspended: bool


class LimitsManager(Manager[Document, LimitState]):
    """Manages limit state, including suspend/resume with persistence."""

    fields: set[str] = {"timeLimit", "energyLimit", "moneyLimit", "suspendLimits"}

    def on_fields_changed(self, doc: Document, changed_fields: set[str]) -> None:
        pass

    _STATE_KEY = "limits"

    async def get_state(self) -> LimitState:
        """Read the current limit state from the device."""
        doc = await self._device.client.get_document()
        return LimitState(
            time=doc.timeLimit,
            energy=doc.energyLimit,
            money=doc.moneyLimit,
            suspended=doc.suspendLimits,
        )

    async def suspend(self) -> None:
        """Save current limits, then suspend all limits on the device."""
        state = await self.get_state()
        self._device.client.save_state(self._STATE_KEY, state)
        await self.set(
            suspendLimits=1,
            timeLimit=0,
            energyLimit=0,
            moneyLimit=0,
        )

    async def resume(self) -> None:
        """Restore previously suspended limits on the device."""
        saved = self._device.client.load_state(self._STATE_KEY)
        if not isinstance(saved, LimitState):
            raise RuntimeError("Saved limit state is corrupted or missing")
        await self.set(
            suspendLimits=0,
            timeLimit=saved.time,
            energyLimit=saved.energy,
            moneyLimit=saved.money,
        )
