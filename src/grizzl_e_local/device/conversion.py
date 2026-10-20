import locale
from datetime import datetime, time
from decimal import Decimal
from collections.abc import Sequence

from ..types import Currency


def minutes_to_time(value: int) -> time:
    """Convert minutes from midnight to a time object."""
    return time(hour=value // 60, minute=value % 60)


def time_to_minutes(t: time) -> int:
    """Convert a time to minutes from midnight."""
    return t.hour * 60 + t.minute


def datetime_to_utc_offset_hours(dt: datetime) -> int:
    offset = dt.utcoffset()
    if offset is None:
        raise ValueError("system time must be timezone-aware")
    return int(offset.total_seconds() // 3600)


def to_currency(value: Decimal | float | str | tuple[int, Sequence[int], int]) -> Currency:
    """Convert device currency (smallest units) to Decimal Currency."""
    frac_digits = locale.localeconv()['frac_digits']
    result = Decimal(value) / (Decimal(10) ** frac_digits)
    return Currency(result.quantize(Decimal(10) ** -frac_digits))


def currency_to_int(c: Currency | Decimal) -> int:
    """Convert a Currency to the device's smallest-units representation."""
    frac_digits = locale.localeconv()['frac_digits']
    return int(c * (10 ** frac_digits))
