from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import NamedTuple, Protocol

from ..types import Currency, PortState, PortSubState, PortErrorState, TimeRange


class State(Protocol):
    async def get(self, attr_name: str) -> object: ...
    async def set(self, attr_name: str, value: object) -> None: ...


class Toggleable(Protocol):
    is_enabled: bool

    def enable(self) -> None: ...
    async def enable_async(self) -> None: ...

    def disable(self) -> None: ...
    async def disable_async(self) -> None: ...

    def toggle(self, on: bool | None = ...) -> None: ...
    async def toggle_async(self, on: bool | None = ...) -> None: ...


class Resetable(Protocol):
    def reset(self) -> None: ...
    async def reset_async(self) -> None: ...


class Valued[T](Protocol):
    value: T


class Ranged(Protocol):
    time_range: TimeRange


class Rate(Valued[Currency], Ranged): ...

class ToggleableFloat(Valued[float], Toggleable): ...

class ToggleableInt(Valued[int], Toggleable): ...


class PrimaryRate(State, Rate):
    @property
    def is_enabled(self) -> bool: ...


class NonPrimaryRate(State, Rate, Toggleable): ...


class Tariffs(State, Sequence[PrimaryRate | NonPrimaryRate]):
    primary_rate: PrimaryRate
    secondary_rate: NonPrimaryRate
    tertiary_rate: NonPrimaryRate
    active_rate_index: int

    def toggle(self, on: bool) -> None: ...
    async def toggle_async(self, on: bool) -> None: ...

    @property
    def active(self) -> PrimaryRate | NonPrimaryRate: ...


class ScheduleEnergyLimit(State, ToggleableFloat): ...

class ScheduleCurrentLimit(State, ToggleableInt): ...


class Schedule(State, Ranged, Toggleable):
    energy_limit: ScheduleEnergyLimit
    current_limit: ScheduleCurrentLimit


class Schedules(State, Toggleable, Sequence[Schedule]):
    first_schedule: Schedule
    second_schedule: Schedule

    def toggle(self, on: bool) -> None: ...
    async def toggle_async(self, on: bool) -> None: ...


class TimeLimit(State, Valued[timedelta], Toggleable): ...

class CostLimit(State, Valued[Currency], Toggleable): ...

class EnergyLimit(State, ToggleableFloat): ...


class Limits(State):
    is_suspended: bool
    is_suspended_once: bool
    time_limit: TimeLimit
    energy_limit: EnergyLimit
    cost_limit: CostLimit

    def suspend(self, once: bool = ...) -> None: ...
    async def suspend_async(self, once: bool = ...) -> None: ...

    def resume(self) -> None: ...
    async def resume_async(self) -> None: ...


class WiFiConfig(State, Toggleable):
    ssid: str
    password: str


class BoundRouter(State):
    connect_via_mac_address: bool
    mac_address: str


class NetworkConfig(State):
    wifi: WiFiConfig
    router: BoundRouter
    ip_address: str


class APConfig(State):
    ssid: str
    password: str


class OCPPConfig(State, Toggleable):
    charge_offline: bool
    is_connected: bool


class Meter(State, Resetable):
    energy: float
    cost: Currency


class Meters(State, Resetable, Sequence[Meter]):
    first: Meter
    second: Meter


class PortStatus(NamedTuple):
    state: PortState
    substate: PortSubState | PortErrorState


class PortSession(State):
    is_active: bool
    duration: timedelta
    energy: float
    cost: Currency


class Port(State):
    voltage: int
    current: int
    power: int
    status: PortStatus
    is_plugged_in: bool
    total_energy: float
    session: PortSession


class Ports(State, Sequence[Port]):
    first: Port
    second: Port
    third: Port


class Version_01(Port, Toggleable):
    """Device state for Firmware 01.XX"""

    username: str
    password: str
    system_time: datetime
    mac_address: str
    ap: APConfig
    network: NetworkConfig
    ocpp: OCPPConfig
    relay_temperature: int
    plug_temperature: int
    limits: Limits
    current_limit: int
    tariffs: Tariffs
    schedules: Schedules
    meters: Meters
    ports: Ports
    is_multiport: bool

    def sync_time(self) -> None: ...
    async def sync_time_async(self) -> None: ...

