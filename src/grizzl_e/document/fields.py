import locale
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BeforeValidator, Field, PlainSerializer

from ..types import Currency


def zero_or_one_to_bool(data: Any) -> Any:
    if data in (0, 1):
        return bool(data)
    return data


def bool_to_int(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    return value


def time_to_minutes(t: time) -> int:
    """Convert a time to minutes from midnight."""
    return t.hour * 60 + t.minute


def minutes_to_time(m: int) -> time:
    """Convert minutes from midnight to a time object."""
    return time(hour=m // 60, minute=m % 60)


def timestamp_to_datetime(value: int) -> datetime:
    td = timedelta(seconds=value)
    td = timedelta(seconds=td.seconds)
    today = datetime.today()
    today = datetime(today.year, today.month, today.day)
    return (today + td)


def timestamp_to_time(value: int) -> time:
    return timestamp_to_datetime(value).time()


def datetime_to_timestamp(value: datetime) -> int:
    return int(value.replace(microsecond=0).timestamp())


def timezone_to_int(value: timezone) -> int:
    offset = value.utcoffset(None)
    return int(offset.total_seconds() // 3600)


def int_to_timezone(value: int) -> timezone:
    return timezone(timedelta(hours=value))


def int_to_currency(value: int) -> Currency:
    frac_digits = locale.localeconv().get('frac_digits')
    result = Decimal(value) / (Decimal(10) ** frac_digits)
    return Currency(result.quantize(Decimal(10) ** (frac_digits * -1)))


def currency_to_int(value: Decimal | int | str | float) -> int:
    if not isinstance(value, Decimal):
        value = Decimal(value)
    frac_digits = locale.localeconv().get('frac_digits')
    return int(value * (10 ** frac_digits))



BoolInt = Annotated[bool, BeforeValidator(zero_or_one_to_bool), PlainSerializer(bool_to_int)]

FrozenBoolInt = Annotated[BoolInt, Field(frozen=True)]

Time = Annotated[time, BeforeValidator(minutes_to_time), PlainSerializer(time_to_minutes)]

DateTime = Annotated[datetime, BeforeValidator(timestamp_to_datetime),
                     PlainSerializer(datetime_to_timestamp)]

TimeZone = Annotated[timezone, BeforeValidator(int_to_timezone), PlainSerializer(timezone_to_int)]

Currency = Annotated[Decimal, BeforeValidator(int_to_currency), PlainSerializer(currency_to_int)]
