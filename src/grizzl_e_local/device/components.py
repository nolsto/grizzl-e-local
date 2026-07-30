from typing import Protocol

from ..types import Currency, TimeRange
from .base import Mutable

MutableBool = Mutable(bool)
MutableInt = Mutable(int)
MutableFloat = Mutable(float)
MutableStr = Mutable(str)

MutableCurrency = Mutable(Currency)
MutableTimeRange = Mutable(TimeRange)


class Valued[T](Protocol):
    value: T


class Ranged(Protocol):
    time_range: TimeRange


class Toggleable(Protocol):
    is_enabled: bool

    def toggle(self, on: bool = False) -> None: ...
    async def toggle_async(self, on: bool = False) -> None: ...


class ToggleableFloat(Valued[float], Toggleable):
    pass


class ToggleableInt(Valued[int], Toggleable):
    pass


class Rate(Valued[Currency], Ranged, Toggleable):
    pass
