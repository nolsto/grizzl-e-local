from __future__ import annotations

import asyncio
from datetime import datetime
from collections.abc import Sequence
from typing import Any

from ..types import TimeRange
from ..util import tznow
from .base import (
    BaseDevice,
    DeviceAttribute as _,
    DeviceComponent,
    DeviceComponentMixin,
    MutableDeviceComponent,
    StateError,
    LazyAttrState,
)
from .components import (
    MutableBool,
    MutableInt,
    MutableFloat,
    MutableStr,
    MutableCurrency,
    MutableTimeRange,
    Ranged,
    Rate,
    Toggleable,
    ToggleableFloat,
    ToggleableInt,
)

class ToggleableState:
    def toggle(self, on: bool | None = None) -> None:
        if on in (True, False):
            self.is_enabled = on
        else:
            self.is_enabled = not self.is_enabled

    async def toggle_async(self, on: bool | None = None) -> None:
        if on in (True, False):
            await self.set("is_enabled", on)
        else:
            await self.set("is_enabled", not self.is_enabled)


class PrimaryRate(DeviceComponent):
    value = _(MutableCurrency, 'tarif')

    class State:
        _node: PrimaryRate  # Static-only — runtime value set by State.__init__

        def __getattr__(self, name: str) -> Any:
            if name in ('time_range', 'is_enabled'):
                return getattr(self._node, name)
            raise AttributeError(name)

    def __init__(self, *args, **kwargs):
        self._is_enabled = True
        self._time_range = TimeRange()
        super().__init__(*args, **kwargs)

    @property
    def time_range(self):
        return self._time_range

    @property
    def is_enabled(self):
        return self._is_enabled


class SecondaryRate(DeviceComponent):
    is_enabled = _(MutableBool, "tarifAEnable")
    value = _(MutableCurrency, value="tarifAValue")
    time_range = _(MutableTimeRange, lower="tarifAStart", upper="tarifAStop")

    state_factory = ToggleableState


class TertiaryRate(DeviceComponent):
    is_enabled = _(MutableBool, "tarifBEnable")
    value = _(MutableCurrency, value="tarifBValue")
    time_range = _(MutableTimeRange, lower="tarifBStart", upper="tarifBStop")

    state_factory = ToggleableState


class Tariffs(DeviceComponent[Rate]):
    primary_rate = _(PrimaryRate)
    secondary_rate = _(SecondaryRate)
    tertiary_rate = _(TertiaryRate)

    class State(Sequence[Rate]):
        _node: Tariffs  # Static-only — runtime value set by State.__init__

        def __getitem__(self, index: int) -> Rate:
            return getattr(self, ["primary_rate", "secondary_rate", "tertiary_rate"][index])

        def __len__(self) -> int:
            return 3

        def toggle(self, on: bool) -> None:
            for rate in list(self)[1:]:
                rate.toggle(on)

        async def toggle_async(self, on: bool) -> None:
            await asyncio.gather(*(rate.toggle_async(on) for rate in list(self)[1:]))

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

    def validate_state(self) -> None:
        active_rates = [r for r in (self.secondary_rate, self.tertiary_rate)
                        if r is not None and r.is_enabled]
        if len(active_rates) > 1:
            for i, a in enumerate(active_rates):
                for b in active_rates[i + 1:]:
                    overlap = a.time_range & b.time_range
                    if overlap is None:
                        continue
                    raise StateError(f"{a} and {b} overlap {overlap}")


class CurrentLimit(DeviceComponentMixin):
    device_limit = _("current_limit")

    @property
    def fields(self) -> set[str]:
        return {*self._device_limit.fields, *super().fields}

    def validate_state(self) -> None:
        if self.value <= 0:
            raise StateError("Amperage must be greater than zero")
        if self.value > self.device_limit:
            raise StateError(
                f"Amperage {self.value} is greater than device limit {self.device_limit}"
            )


class EnergyLimitMixin(DeviceComponentMixin):
    # TODO: Use energy limitation if it is set
    pass


class FirstScheduleEnergyLimit(EnergyLimitMixin, DeviceComponent):
    is_enabled = _(MutableBool, "sh1EnergyEnable")
    value = _(MutableFloat, "sh1EnergyValue")


class FirstScheduleCurrentLimit(CurrentLimit, DeviceComponent):
    is_enabled = _(MutableBool, "sh1CurrentEnable")
    value = _(MutableInt, "sh1CurrentValue")

    @property
    def fields(self) -> set[str]:
        return {"sh1CurrentValue", *super().fields}


class FirstSchedule(DeviceComponent):
    is_enabled = _(MutableBool, "sh1Enabled")
    time_range = _(MutableTimeRange, lower="sh1Start", upper="sh1Stop")
    energy_limit = _(FirstScheduleEnergyLimit)
    current_limit = _(FirstScheduleCurrentLimit)

    state_factory = ToggleableState


class SecondScheduleEnergyLimit(EnergyLimitMixin, DeviceComponent):
    is_enabled = _(MutableBool, "sh2EnergyEnable")
    value = _(MutableFloat, "sh2EnergyValue")


class SecondScheduleCurrentLimit(CurrentLimit, DeviceComponent):
    is_enabled = _(MutableBool, "sh2CurrentEnable")
    value = _(MutableInt, "sh2CurrentValue")

    @property
    def fields(self) -> set[str]:
        return {"sh2CurrentValue", *super().fields}


class SecondSchedule(DeviceComponent):
    is_enabled = _(MutableBool, "sh2Enabled")
    time_range = _(MutableTimeRange, lower="sh2Start", upper="sh2Stop")
    energy_limit = _(SecondScheduleEnergyLimit)
    current_limit = _(SecondScheduleCurrentLimit)

    state_factory = ToggleableState


class Schedule(Ranged, Toggleable):
    energy_limit: ToggleableFloat
    current_limit: ToggleableInt


class Schedules(DeviceComponent):
    first_schedule = _(FirstSchedule)
    second_schedule = _(SecondSchedule)

    class State(Sequence):
        _node: Schedules  # Static-only — runtime value set by State.__init__

        def __getitem__(self, index: int) -> Schedule:
            return getattr(self, ["first_schedule", "second_schedule"][index])

        def __len__(self) -> int:
            return 2

        def toggle(self, on: bool) -> None:
            for schedule in self:
                schedule.toggle(on)

        async def toggle_async(self, on: bool) -> None:
            await asyncio.gather(*(schedule.toggle_async(on) for schedule in self))


class TimeLimit(DeviceComponent):
    is_enabled = _(MutableBool, "timeLimitS")
    value = _(MutableCurrency, "timeLimit")


class CostLimit(DeviceComponent):
    is_enabled = _(MutableBool, "moneyLimitS")
    value = _(MutableCurrency, "moneyLimit")


class EnergyLimit(DeviceComponent):
    is_enabled = _(MutableBool, "energyLimitS")
    value = _(MutableFloat, "energyLimit")


class Limits(DeviceComponent):
    is_suspended = _(MutableBool, "suspendLimits")
    is_suspended_once = _(MutableBool, "oneCharge")
    time_limit = _(TimeLimit)
    energy_limit = _(EnergyLimit)
    cost_limit = _(CostLimit)

    class State:
        _node: Limits  # Static-only — runtime value set by State.__init__

        def suspend(self, once: bool = False) -> None:
            if once:
                self.is_suspended_once = True
            else:
                self.is_suspended = True

        async def suspend_async(self, once: bool = False) -> None:
            if once:
                await self.set("is_suspended_once", True)
            else:
                await self.set("is_suspended", True)

        def resume(self) -> None:
            self.is_suspended = self.is_suspended_once = False

        async def resume_async(self) -> None:
            await asyncio.gather(
                self.set("is_suspended_once", False),
                self.set("is_suspended", False),
            )


class WiFiConfig(DeviceComponent):
    is_enabled = _(MutableBool, "WifiMode")
    ssid = _(MutableStr, "ssidName")
    password = _(MutableStr, "ssidPassword")

    state_factory = ToggleableState

    def get_field_value(self, field: str):
        value = super().get_field_value(field)
        if field == "WifiMode":
            value = value == 3
        return value


class BoundRouter(DeviceComponent):
    connect_via_mac_address = _(MutableBool, "mac_bind")
    mac_address = _(MutableStr, "STA_MAC")
    # TODO: Use this to determine if in conflict state:
    # WiFi is not enabled, but connect_via_mac_address is.
    wifi_is_enabled = _('network.wifi.is_enabled')


class NetworkConfig(DeviceComponent):
    wifi = _(WiFiConfig)
    router = _(BoundRouter)
    ip_address = _(str, "STA_IP_Addres")


class APConfig(DeviceComponent):
    ssid = _(MutableStr, "ssidNameAP")
    password = _(MutableStr, "ssidPasswordAP")


class OCPPConfig(DeviceComponent):
    is_enabled = _(MutableBool, "ocppEnabled")
    charge_offline = _(MutableBool, "ocppOfflineAva")
    is_connected = _(bool, "ocppconnected")

    state_factory = ToggleableState


class SystemTime(MutableDeviceComponent[datetime]):
    """Device timezone and system time as timezone-aware datetime"""

    state_factory = datetime.fromtimestamp

    def __init__(self, *args):
        super().__init__(*args, "systemTime", "timeZone")

    def get_field_value(self, field: str):
        value = super().get_field_value(field)
        if field == "systemTime":
            assert isinstance(value, datetime)
            return value.timestamp()
        return value

    def get_field_values(self):
        return {
            "systemTime": self._state,
            "timeZone": self._state.tzinfo,
        }


class Version_01(BaseDevice):
    """Base device for Firmware 01.XX"""

    username = _(MutableStr, "httpUsername")
    password = _(MutableStr, "httpPassword")
    system_time = _(SystemTime)
    mac_address = _(str, "ESP_MAC")
    ap = _(APConfig)
    network = _(NetworkConfig)
    ocpp = _(OCPPConfig)
    limits = _(Limits)
    current_limit = _(MutableInt, "currentSet")
    tariffs = _(Tariffs)
    schedules = _(Schedules)

    class State:
        _node: Version_01  # Static-only — runtime value set by State.__init__

        def sync_time(self) -> None:
            self._node.set_fields({"systemTime": tznow, "timeZone": lambda: tznow().tzinfo})

        async def sync_time_async(self) -> None:
            await self._node.set_fields_async(
                {"systemTime": tznow, "timeZone": lambda: tznow().tzinfo}
            )


class Version_01_01(Version_01):
    """Device for Firmware 01.01"""
    pass


Device = Version_01_01
