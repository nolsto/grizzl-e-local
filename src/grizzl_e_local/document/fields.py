import locale
from datetime import datetime, time, timedelta, timezone, tzinfo
from decimal import Decimal
from collections.abc import Callable

from ..types import Currency


def minutes_to_time(value: int) -> time:
    """Convert minutes from midnight to a time object."""
    return time(hour=value // 60, minute=value % 60)


def time_to_minutes(t: time) -> int:
    """Convert a time to minutes from midnight."""
    return t.hour * 60 + t.minute


def timestamp_to_datetime(value: int) -> datetime:
    """Convert Unix timestamp (seconds since epoch) to datetime."""
    return datetime.fromtimestamp(value)


def datetime_to_timestamp(dt: datetime) -> int:
    """Convert a datetime to Unix timestamp (seconds since epoch)."""
    return int(dt.timestamp())


def offset_to_timezone(value: int) -> tzinfo:
    """Convert hours offset from UTC to timezone object."""
    return timezone(timedelta(hours=value))


def timezone_to_int(tz: tzinfo) -> int:
    """Convert a timezone to hours offset from UTC."""
    return int(tz.utcoffset(None).total_seconds() // 3600)


def to_currency(value: int) -> Currency:
    """Convert device currency (cents/pennies) to Decimal Currency."""
    frac_digits = locale.localeconv()['frac_digits']
    result = Decimal(value) / (Decimal(10) ** frac_digits)
    return Currency(result.quantize(Decimal(10) ** -frac_digits))


def currency_to_int(c: Currency | Decimal) -> int:
    """Convert a Currency to device representation (cents/pennies)."""
    frac_digits = locale.localeconv()['frac_digits']
    return int(c * (10 ** frac_digits))


# Registry: canonical type → (deserializer, serializer, *raw input types)
FIELD_CONVERSIONS: dict[type, tuple[Callable, Callable, *tuple[type]]] = {
    bool:       (bool, int, int),
    time:       (minutes_to_time, time_to_minutes, int),
    datetime:   (timestamp_to_datetime, datetime_to_timestamp, int),
    tzinfo:     (offset_to_timezone, timezone_to_int, int),
    Decimal:    (to_currency, currency_to_int, int),  # Currency is a subclass of Decimal
}
