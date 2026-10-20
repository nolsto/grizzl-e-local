from collections import namedtuple
from datetime import time, timedelta

from ..types import Currency, PortState, TimeRange
from .base import DeviceComponent, Mutable, MutableDeviceComponent
from .conversion import currency_to_int, minutes_to_time, time_to_minutes, to_currency


MutableInt = Mutable(int)
MutableFloat = Mutable(float)
MutableStr = Mutable(str)

# Firmware encodes boolean values as 0/1 integers.
class MutableBool(MutableDeviceComponent[bool]):
    state_factory = bool

    def to_fields(self):
        return {self.field_args[0]: int(self._state)}


class InvertedMutableBool(MutableDeviceComponent[bool]):
    @staticmethod
    def state_factory(value):
        return not bool(value)

    def to_fields(self):
        return {self.field_args[0]: int(not self._state)}


class MutableCurrency(MutableDeviceComponent[Currency]):
    @staticmethod
    def state_factory(value, /):
        return to_currency(value)

    def to_fields(self):
        return {self.field_args[0]: currency_to_int(self._state)}


class MutableTimeDelta(MutableDeviceComponent[timedelta]):
    @staticmethod
    def state_factory(*, seconds):
        return timedelta(seconds=seconds)

    def to_fields(self):
        value = int(self._state.total_seconds())
        field = next(iter(self.field_kwargs.values()))
        return {field: value}


class MutableTimeRange(MutableDeviceComponent[TimeRange]):
    state_factory = TimeRange

    def get_field_value(self, field: str) -> time:
        return minutes_to_time(super().get_field_value(field))

    def to_fields(self):
        return {f: time_to_minutes(getattr(self._state, k)) for k, f in self.field_kwargs.items()}


class PlugConnection(DeviceComponent[bool | None]):
    @staticmethod
    def state_factory(value):
        if value == 0:
            return False
        if value in (1, 2):
            return True
        return None  # state of connection is not available


class _PortStatusState(namedtuple("_PortStatusState", "state substate")):
    def __str__(self) -> str:
        return f"{self.state}: {self.substate}"


class PortStatus(DeviceComponent):
    @staticmethod
    def state_factory(*, state: int, substate: int):
        state = PortState(state)
        substate = state.get_substate(substate)
        return _PortStatusState(state, substate)
