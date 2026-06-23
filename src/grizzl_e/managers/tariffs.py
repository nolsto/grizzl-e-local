from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from ..document import Document
from ..managers import Manager
from ..types import Conflict, Rate, TimeRange, _minutes_to_time, _time_to_minutes

if TYPE_CHECKING:
    from ..client import Client


@dataclass(frozen=True)
class TariffState:
    primary: Decimal
    rate2: Rate | None
    rate3: Rate | None
    conflicts: list[Conflict]


def _find_overlaps(rates: list[Rate]) -> list[Conflict]:
    """Find all pairwise time-range overlaps among the given rates."""
    conflicts: list[Conflict] = []
    for i, a in enumerate(rates):
        for b in rates[i + 1 :]:
            if a.time_range.overlaps(b.time_range):
                overlap = a.time_range.intersection(b.time_range)
                if overlap is None:
                    continue
                conflicts.append(Conflict(
                    rates=(a.name, b.name),
                    overlap=overlap,
                    message=f"{a.name} and {b.name} overlap {overlap}",
                ))
    return conflicts


def _doc_to_tariff_state(doc: Document) -> TariffState:
    """Convert a Document into a TariffState."""
    primary = Decimal(str(doc.tarifAValue if doc.tarifAEnable else doc.tarif))

    rate2: Rate | None = None
    if doc.tarifAEnable and not (doc.tarifAStart == 0 and doc.tarifAStop == 0):
        rate2 = Rate(
            name="rate2",
            value=Decimal(str(doc.tarifAValue)),
            time_range=TimeRange(
                lower=_minutes_to_time(doc.tarifAStart),
                upper=_minutes_to_time(doc.tarifAStop),
            ),
        )

    rate3: Rate | None = None
    if doc.tarifBEnable and not (doc.tarifBStart == 0 and doc.tarifBStop == 0):
        rate3 = Rate(
            name="rate3",
            value=Decimal(str(doc.tarifBValue)),
            time_range=TimeRange(
                lower=_minutes_to_time(doc.tarifBStart),
                upper=_minutes_to_time(doc.tarifBStop),
            ),
        )

    active_rates = [r for r in (rate2, rate3) if r is not None]
    conflicts = _find_overlaps(active_rates)

    return TariffState(
        primary=primary,
        rate2=rate2,
        rate3=rate3,
        conflicts=conflicts,
    )


class TariffManager(Manager):
    """Manages tariff state: read, validate, and write to the device."""

    async def get(self) -> TariffState:
        """Read the current tariff state from the device."""
        doc = await self._client.get_document()
        return _doc_to_tariff_state(doc)

    async def set_primary(self, primary: Decimal) -> None:
        await self.set(tarif=int(primary))

    async def set_rates(
        self,
        rate2: Rate | None = None,
        rate3: Rate | None = None,
    ) -> None:
        """Validate and write tariff settings to the device.

        Raises ValueError if the proposed rates overlap.
        """
        # Build the full set of active rates for validation
        active_rates: list[Rate] = []
        if rate2 is not None:
            active_rates.append(rate2)
        if rate3 is not None:
            active_rates.append(rate3)

        conflicts = _find_overlaps(active_rates)
        if conflicts:
            raise ValueError("Tariff time ranges overlap: " + "; ".join(c.message for c in conflicts))

        # Build the full set of keys to write
        data: dict[str, Any] = {}
        if rate2 is not None:
            data["tarifAEnable"] = 1
            data["tarifAValue"] = int(rate2.value)
            data["tarifAStart"] = _time_to_minutes(rate2.time_range.lower)
            data["tarifAStop"] = _time_to_minutes(rate2.time_range.upper)
        else:
            data["tarifAEnable"] = 0

        if rate3 is not None:
            data["tarifBEnable"] = 1
            data["tarifBValue"] = int(rate3.value)
            data["tarifBStart"] = _time_to_minutes(rate3.time_range.lower)
            data["tarifBStop"] = _time_to_minutes(rate3.time_range.upper)
        else:
            data["tarifBEnable"] = 0

        await self.set(**data)
