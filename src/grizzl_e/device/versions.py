from datetime import datetime
from typing import Protocol
from collections.abc import Iterator

from ..types import Currency, WraparoundTimeRange
from .base import (
    BaseDevice,
    ComponentStateError,
    DeviceAttribute as _,
    DeviceComponent,
    DeviceComponentMixin,
    MutableDeviceComponent,
    Mutable,
)


class Valued[T](Protocol):
    value: T


class Ranged(Protocol):
    time_range: WraparoundTimeRange


class Toggleable(Protocol):
    is_enabled: bool


class ToggleableFloat(Valued[float], Toggleable):
    pass


class ToggleableInt(Valued[int], Toggleable):
    pass


class Rate(Valued[Currency], Ranged, Toggleable):
    pass


class PrimaryRate(DeviceComponent):
    value = _(Mutable(Currency), 'tarif')

    def __init__(self, *args, **kwargs):
        self._time_range = WraparoundTimeRange()
        self._is_enabled = True
        super().__init__(*args, **kwargs)

    @property
    def time_range(self):
        return self._time_range

    @property
    def is_enabled(self):
        return self._is_enabled

    def get_state_factory(self):
        class PrimaryRateState(self.state_factory):  # type: ignore[invalid-inheritance]
            def __getattr__(self, name):
                if name in ('time_range', 'is_enabled'):
                    return getattr(self.node, name)
                return super().__getattr__(name)

        return PrimaryRateState


class SecondaryRate(DeviceComponent):
    value = _(Mutable(Currency), value="tarifAValue")
    time_range = _(Mutable(WraparoundTimeRange), lower="tarifAStart", upper="tarifAStop")
    is_enabled = _(Mutable(bool), "tarifAEnable")


class TertiaryRate(DeviceComponent):
    value = _(Mutable(Currency), value="tarifBValue")
    time_range = _(Mutable(WraparoundTimeRange), lower="tarifBStart", upper="tarifBStop")
    is_enabled = _(Mutable(bool), "tarifBEnable")


class Tariffs(DeviceComponent[Rate]):
    primary_rate = _(PrimaryRate)
    secondary_rate = _(SecondaryRate)
    tertiary_rate = _(TertiaryRate)

    @property
    def fields(self) -> set[str]:
        return {
            "tarifAEnable",
            "tarifBEnable",
            "tarifAStart",
            "tarifBStart",
            "tarifAStop",
            "tarifBStop",
            *super().fields
        }

    def get_state_factory(self):
        class TariffState(self.state_factory):  # type: ignore[invalid-inheritance]
            def __iter__(self) -> Iterator[Rate]:
                return iter([
                    self.node.primary_rate,
                    self.node.secondary_rate,
                    self.node.tertiary_rate,
                ])

        return TariffState

    def on_fields_changed(self, *args, **kwargs) -> None:
        with self.exception_state() as exceptions:
            active_rates = [r for r in (self.secondary_rate, self.tertiary_rate)
                            if r is not None and r.is_enabled]
            if len(active_rates) > 1:
                for i, a in enumerate(active_rates):
                    for b in active_rates[i + 1:]:
                        overlap = a.time_range & b.time_range
                        if overlap is None:
                            continue
                        exceptions.append(ComponentStateError(f"{a} and {b} overlap {overlap}"))


class CurrentLimit(DeviceComponentMixin):
    device_limit = _("current_limit")

    @property
    def fields(self: DeviceComponent) -> set[str]:
        return {self._device_limit.attr_name, *super().fields}

    def on_fields_changed(self: DeviceComponent, changed_fields: set[str]) -> None:
        with self.exception_state():
            pass


class EnergyLimit(DeviceComponentMixin):
    # TODO: Use energy limitation if it is set
    pass


class FirstScheduleEnergyLimit(EnergyLimit, DeviceComponent):
    is_enabled = _(Mutable(bool), "sh1EnergyEnable")
    value = _(Mutable(float), "sh1EnergyValue")


class FirstScheduleCurrentLimit(CurrentLimit, DeviceComponent):
    is_enabled = _(Mutable(bool), "sh1CurrentEnable")
    value = _(Mutable(int), "sh1CurrentValue")

    @property
    def fields(self) -> set[str]:
        return {"sh1CurrentEnable", "sh1CurrentValue", *super().fields}


class FirstSchedule(DeviceComponent):
    time_range = _(Mutable(WraparoundTimeRange), lower="sh1Start", upper="sh1Stop")
    is_enabled = _(Mutable(bool), "sh1Enabled")
    energy_limit = _(FirstScheduleEnergyLimit)
    current_limit = _(FirstScheduleCurrentLimit)


class SecondScheduleEnergyLimit(EnergyLimit):
    is_enabled = _(Mutable(bool), "sh2EnergyEnable")
    value = _(Mutable(float), "sh2EnergyValue")


class SecondScheduleCurrentLimit(CurrentLimit, DeviceComponent):
    is_enabled = _(Mutable(bool), "sh2CurrentEnable")
    value = _(Mutable(int), "sh2CurrentValue")

    @property
    def fields(self) -> set[str]:
        return {"sh2CurrentEnable", "sh2CurrentValue", *super().fields}


class SecondSchedule(DeviceComponent):
    time_range = _(Mutable(WraparoundTimeRange), lower="sh2Start", upper="sh2Stop")
    is_enabled = _(Mutable(bool), "sh2Enabled")
    energy_limit = _(SecondScheduleEnergyLimit)
    current_limit = _(SecondScheduleCurrentLimit)


class Schedule(Ranged, Toggleable):
    energy_limit: ToggleableFloat
    current_limit: ToggleableInt


class Schedules(DeviceComponent):
    first_schedule = _(FirstSchedule)
    second_schedule = _(SecondSchedule)

    def get_state_factory(self):
        class SchedulesState(self.state_factory):  # type: ignore[invalid-inheritance]
            def __iter__(self) -> Iterator[Schedule]:
                return iter([self.node.first_schedule, self.node.second_schedule])

        return SchedulesState


class SystemTime(MutableDeviceComponent):
    """Manages device timezone and system time as timezone-aware datetimes."""

    def __init__(self, *args):
        super().__init__(*args, "systemTime", "timeZone")

    def get_state_factory(self):
        return datetime.fromtimestamp

    def get_field_value(self, field: str):
        value = super().get_field_value(field)
        if field == "systemTime":
            assert isinstance(value, datetime)
            return value.timestamp()
        return value


class Version_01(BaseDevice):
    """Base device for Firmware 01.XX"""

    system_time = _(SystemTime)
    current_limit = _(Mutable(int), "currentSet")
    tariffs = _(Tariffs)
    schedules = _(Schedules)


class Version_01_01(Version_01):
    """Device for Firmware 01.01"""
    pass


Device = Version_01_01
