from __future__ import annotations

import locale
from decimal import Decimal
from typing import TYPE_CHECKING, TypeVar

from .ranges import WraparoundTimeRange as TimeRange

if TYPE_CHECKING:
    from ..document import BaseDocument
    from ..device import BaseDevice

__all__ = ["DocT", "DeviceT", "Currency", "TimeRange"]

DocT = TypeVar("DocT", bound="BaseDocument")
DeviceT = TypeVar("DeviceT", bound="BaseDevice")


class Currency(Decimal):
    def __str__(self):
        return locale.currency(self, grouping=True)
