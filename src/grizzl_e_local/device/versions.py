from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import cast, no_type_check, Any

from ..types import Currency, TimeRange
from ..util import tznow
from .base import (
    component_from_type,
    BaseDevice,
    DeviceAttribute as _,
    DeviceComponent,
    DeviceComponentMixin,
    MutableDeviceComponent,
    StateError,
)
from .conversion import datetime_to_utc_offset_hours
from .components import (
    InvertedMutableBool,
    MutableBool,
    MutableInt,
    MutableFloat,
    MutableStr,
    MutableCurrency,
    MutableTimeRange,
    MutableTimeDelta,
    PlugConnection,
    PortStatus,
)
from .state import State


class Toggleable:
    def enable(self) -> None:
        self.toggle(on=True)

    async def enable_async(self) -> None:
        await self.toggle_async(on=True)

    def disable(self) -> None:
        self.toggle(on=False)

    async def disable_async(self) -> None:
        await self.toggle_async(on=False)

    def toggle(self, on: bool | None = None) -> None:
        raise NotImplementedError

    async def toggle_async(self, on: bool | None = None) -> None:
        raise NotImplementedError


class ToggleableState(Toggleable, State):
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

    class State(State):
        _node: "PrimaryRate"

        def __getattr__(self, name: str) -> Any:
            try:
                return super().__getattr__(name)  # type: ignore[reportAttributeAccessIssue]
            except AttributeError:
                if name in ('time_range', 'is_enabled'):
                    return getattr(self._node, name)
                raise

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
    value = _(MutableCurrency, "tarifAValue")
    time_range = _[TimeRange](MutableTimeRange, lower="tarifAStart", upper="tarifAStop")

    state_factory = ToggleableState


class TertiaryRate(DeviceComponent):
    is_enabled = _(MutableBool, "tarifBEnable")
    value = _(MutableCurrency, "tarifBValue")
    time_range = _[TimeRange](MutableTimeRange, lower="tarifBStart", upper="tarifBStop")

    state_factory = ToggleableState


class Tariffs(DeviceComponent):
    primary_rate = _(PrimaryRate)
    secondary_rate = _(SecondaryRate)
    tertiary_rate = _(TertiaryRate)
    active_rate_index = _(int, "activeTarif")

    class State(Toggleable, State, Sequence):
        def __getitem__(self, index: int):
            return getattr(self, ["primary_rate", "secondary_rate", "tertiary_rate"][index])

        def __len__(self) -> int:
            return 3

        def toggle(self, on: bool) -> None:
            for rate in list(self)[1:]:
                cast(Toggleable, rate).toggle(on)

        async def toggle_async(self, on):
            await asyncio.gather(
                *(rate.toggle_async(on) for rate in list(self)[1:])
            )

        @property
        def active(self):
            return self[self.active_rate_index]  #type: ignore[reportAttributeAccessIssue]


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


class LimitMixin:
    @property
    @no_type_check
    def fields(self) -> set[str]:
        return {*self._device_limit.fields, *super().fields}

    @no_type_check
    def validate_state(self) -> None:
        if self.value <= 0:
            raise StateError("Value must be greater than zero")
        if self.value > self.device_limit:
            raise StateError(
                f"Value {self.value} is greater than device limit {self.device_limit}"
            )


class CurrentLimitMixin(DeviceComponentMixin, LimitMixin):
    device_limit = _("current_limit")


class EnergyLimitMixin(DeviceComponentMixin, LimitMixin):
    device_limit = _("limits.energy_limit.value")


class FirstScheduleEnergyLimit(EnergyLimitMixin, DeviceComponent):
    is_enabled = _(MutableBool, "sh1EnergyEnable")
    value = _(MutableFloat, "sh1EnergyValue")

    state_factory = ToggleableState


class FirstScheduleCurrentLimit(CurrentLimitMixin, DeviceComponent):
    is_enabled = _(MutableBool, "sh1CurrentEnable")
    value = _(MutableInt, "sh1CurrentValue")

    state_factory = ToggleableState

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

    state_factory = ToggleableState


class SecondScheduleCurrentLimit(CurrentLimitMixin, DeviceComponent):
    is_enabled = _(MutableBool, "sh2CurrentEnable")
    value = _(MutableInt, "sh2CurrentValue")

    state_factory = ToggleableState

    @property
    def fields(self) -> set[str]:
        return {"sh2CurrentValue", *super().fields}


class SecondSchedule(DeviceComponent):
    is_enabled = _(MutableBool, "sh2Enabled")
    time_range = _(MutableTimeRange, lower="sh2Start", upper="sh2Stop")
    energy_limit = _(SecondScheduleEnergyLimit)
    current_limit = _(SecondScheduleCurrentLimit)

    state_factory = ToggleableState


class Schedules(DeviceComponent):
    first_schedule = _(FirstSchedule)
    second_schedule = _(SecondSchedule)

    class State(Toggleable, State, Sequence):
        def __getitem__(self, index):
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
    value = _(MutableTimeDelta, seconds="timeLimit")

    state_factory = ToggleableState


class CostLimit(DeviceComponent):
    is_enabled = _(MutableBool, "moneyLimitS")
    value = _(MutableCurrency, "moneyLimit")

    state_factory = ToggleableState


class EnergyLimit(DeviceComponent):
    is_enabled = _(MutableBool, "energyLimitS")
    value = _(MutableFloat, "energyLimit")

    state_factory = ToggleableState


class Limits(DeviceComponent):
    is_suspended = _(MutableBool, "suspendLimits")
    is_suspended_once = _(MutableBool, "oneCharge")
    time_limit = _(TimeLimit)
    energy_limit = _(EnergyLimit)
    cost_limit = _(CostLimit)

    class State(State):
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


class FirstMeter(DeviceComponent):
    energy = _(float, "IEM1")
    cost = _(Currency, "IEM1_money")

    class State(State):
        _node: "FirstMeter"

        def reset(self) -> None:
            self._node.set_fields({"rstEM1": None})

        async def reset_async(self) -> None:
            await self._node.set_fields_async({"rstEM1": None})


class SecondMeter(DeviceComponent):
    energy = _(float, "IEM2")
    cost = _(Currency, "IEM2_money")

    class State(State):
        _node: "SecondMeter"

        def reset(self) -> None:
            self._node.set_fields({"rstEM2": None})

        async def reset_async(self) -> None:
            await self._node.set_fields_async({"rstEM2": None})


class Meters(DeviceComponent):
    first = _(FirstMeter)
    second = _(SecondMeter)

    class State(State, Sequence):
        def __getitem__(self, index: int):
            return getattr(self, ["first", "second"][index])

        def __len__(self) -> int:
            return 2

        def reset(self) -> None:
            for meter in self:
                meter.reset()

        async def reset_async(self) -> None:
            await asyncio.gather(*(meter.reset() for meter in self))


class PortMixin(DeviceComponentMixin):
    voltage = _(int, "voltMeas1")


class FirstPortSession(DeviceComponent):
    is_active = _(bool, "sessionStarted")
    duration = _(timedelta, seconds="sessionTime")
    energy = _(float, "sessionEnergy")
    cost = _(Currency, "sessionMoney")


class FirstPort(PortMixin, DeviceComponent):
    current = _(int, "curMeas1")
    power = _(int, "powerMeas")
    status = _(PortStatus, state="state", substate="subState")
    is_plugged_in = _(PlugConnection, "pilot")
    total_energy = _(float, "totalEnergy")
    session = _(FirstPortSession)


class SecondPortSession(DeviceComponent):
    is_active = _(bool, "sessionStarted2")
    duration = _(timedelta, seconds="sessionTime2")
    energy = _(float, "sessionEnergy2")
    cost = _(Currency, "sessionMoney2")


class SecondPort(PortMixin, DeviceComponent):
    current = _(int, "curMeas1C2")
    power = _(int, "powerMeas2")
    status = _(PortStatus, state="state2", substate="subState2")
    is_plugged_in = _(PlugConnection, "pilot2")
    total_energy = _(float, "totalEnergy2")
    session = _(SecondPortSession)


class ThirdPortSession(DeviceComponent):
    is_active = _(bool, "sessionStarted3")
    duration = _(timedelta, seconds="sessionTime3")
    energy = _(float, "sessionEnergy3")
    cost = _(Currency, "sessionMoney3")


class ThirdPort(PortMixin, DeviceComponent):
    current = _(int, "curMeas1C3")
    power = _(int, "powerMeas3")
    status = _(PortStatus, state="state3", substate="subState3")
    is_plugged_in = _(PlugConnection, "pilot3")
    total_energy = _(float, "totalEnergy3")
    session = _(ThirdPortSession)

    def __init__(self, *args, **kwargs):
        self.is_plugged_in


class Ports(DeviceComponent):
    first = _(FirstPort)
    second = _(SecondPort)
    third = _(ThirdPort)
    has_multiple = _("is_multiport")

    class State(State):
        def __getitem__(self, index: int):
            if not self.has_multiple and index > 0:  # type: ignore[reportAttributeAccessIssue]
                raise IndexError
            return getattr(self, ["first", "second", "third"][index])

        def __len__(self) -> int:
            return 3 if self.has_multiple else 1  # type: ignore[reportAttributeAccessIssue]


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
    wifi_is_enabled = _('network.wifi.is_enabled')

    def validate_state(self) -> None:
        if self.connect_via_mac_address and not self.wifi_is_enabled:
            raise StateError("Cannot connect via MAC address when device WiFi is disabled")


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
    """Device timezone and system time as timezone-aware datetime."""

    @staticmethod
    def state_factory(*, hours: int, offset_hours: int) -> datetime:
        offset = timezone(timedelta(hours=offset_hours))
        return datetime.fromtimestamp(hours).astimezone(offset)

    def to_fields(self):
        return {
            self.field_kwargs["hours"]: int(self._state.timestamp()),
            self.field_kwargs["offset_hours"]: datetime_to_utc_offset_hours(self._state),
        }


class MultiPortEVSE(component_from_type(bool)):
    def get_field_value(self, field: str):
        return False if super().get_field_value(field) == 1 else True


class Version_01(BaseDevice):
    """Device for Firmware 01.XX"""

    username = _(MutableStr, "httpUsername")
    password = _(MutableStr, "httpPassword")
    system_time = _(SystemTime, hours="systemTime", offset_hours="timeZone")
    mac_address = _(str, "ESP_MAC")
    ap = _(APConfig)
    network = _(NetworkConfig)
    ocpp = _(OCPPConfig)
    is_enabled = _(InvertedMutableBool, "evseEnabled")
    relay_temperature = _(int, "temperature1")
    plug_temperature = _(int, "temperature2")
    limits = _(Limits)
    current_limit = _(MutableInt, "currentSet")
    tariffs = _(Tariffs)
    schedules = _(Schedules)
    meters = _(Meters)
    ports = _(Ports)
    is_multiport = _(MultiPortEVSE, "typeEvse")

    class State(ToggleableState):
        _node: "Version_01"

        def __getattr__(self, name: str) -> Any:
            try:
                return super().__getattr__(name)  # type: ignore[reportAttributeAccessIssue]
            except AttributeError:
                # Allow accessing attributs of first port directly on the device.
                return getattr(self.ports[0], name)

        def sync_time(self) -> None:
            self._node.set_fields({
                "systemTime": lambda: int(tznow().timestamp()),
                "timeZone": lambda: datetime_to_utc_offset_hours(tznow()),
            })

        async def sync_time_async(self) -> None:
            await self._node.set_fields_async({
                "systemTime": lambda: int(tznow().timestamp()),
                "timeZone": lambda: datetime_to_utc_offset_hours(tznow()),
            })

        def clear_auth(self) -> None:
            self._node.set_fields({"httpUsername": "", "httpPassword": ""})

        async def clear_auth_async(self) -> None:
            await self._node.set_fields_async({"httpUsername": "", "httpPassword": ""})
