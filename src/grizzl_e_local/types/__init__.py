from __future__ import annotations

import gettext
import locale
from decimal import Decimal
from typing import TYPE_CHECKING, TypeVar

from .enum import IntEnum
from .ranges import WraparoundTimeRange as TimeRange

if TYPE_CHECKING:
    from ..document import BaseDocument
    from ..device import BaseDevice

__all__ = ["DocT", "DeviceT", "Currency", "TimeRange"]

DocT = TypeVar("DocT", bound="BaseDocument")
DeviceT = TypeVar("DeviceT", bound="BaseDevice")

_ = gettext.gettext


class Currency(Decimal):
    def __str__(self):
        return locale.currency(self, grouping=True)


class PortState(IntEnum):
    POWER_UP = 0
    SELF_TEST = 1
    STANDBY = 2
    CAR_CONNECTED = 3
    CAR_CHARGING = 4
    CHARGING_COMPLETE = 5
    DISABLED = 6
    ERROR = 7

    class Labels:
        POWER_UP = _("Power Up")
        SELF_TEST = _("Self-Test")
        STANDBY = _("Standby")
        CAR_CONNECTED = _("Car Connected")
        CAR_CHARGING = _("Car Charging")
        CHARGING_COMPLETE = _("Charging Complete")
        DISABLED = _("Disabled")
        ERROR = _("Error")

    def get_substate(self, index: int):
        return {PortState.ERROR: PortErrorState}.get(self, PortSubState)(index)


class PortErrorState(IntEnum):
    NO_ERRORS = 0
    PROTECTIVE_EARTH_FAULT = 1
    GFCI_HIGH = 2
    RELAY_FAULT = 3
    GFCI_LOW = 4
    RELAY_OVERTEMPERTURE = 5
    PLUG_OVERTRTEMPERATURE = 6
    PILOT_FAULT = 7
    LOW_VOLTAGE = 8
    DIODE_FAULT = 9
    OVER_CURRENT = 10
    INTERFACE_TIMEOUT = 11
    APPLICATION_ERROR = 12
    GFCI_TEST_FAILURE = 13
    HIGH_VOLTAGE = 14

    class Labels:
        NO_ERRORS = _("No Errors")
        PROTECTIVE_EARTH_FAULT = _("Protective Earth Fault")
        GFCI_HIGH = _("Leakage High")
        RELAY_FAULT = _("Relay Fault")
        GFCI_LOW = _("Leakage Low")
        RELAY_OVERTEMPERTURE = _("Overtemperature B")
        PLUG_OVERTRTEMPERATURE = _("Overtemperature P")
        PILOT_FAULT = _("Pilot Fault")
        LOW_VOLTAGE = _("Undervoltage")
        DIODE_FAULT = _("Diode Fault")
        OVER_CURRENT = _("Overcurrent")
        INTERFACE_TIMEOUT = _("Interface Timeout")
        APPLICATION_ERROR = _("Application Error")
        GFCI_TEST_FAILURE = _("GFCI Test Failed")
        HIGH_VOLTAGE = _("Overvoltage")


class PortSubState(IntEnum):
    NO_LIMITS = 0
    USER_LIMIT = 1
    ENERGY_LIMIT = 2
    TIME_LIMIT = 3
    COST_LIMIT = 4
    SCHEDULE_1_TIME_LIMIT = 5
    SCHEDULE_1_ENERGY_LIMIT = 6
    SCHEDULE_2_TIME_LIMIT = 7
    SCHEDULE_2_ENERGY_LIMIT = 8
    EXTERNAL_LIMIT = 9

    class Labels:
        NO_LIMITS = _("No limits")
        USER_LIMIT = _("Limited by User")
        ENERGY_LIMIT = _("Limited by Energy")
        TIME_LIMIT = _("Limited by Time")
        COST_LIMIT = _("Limited by Cost")
        SCHEDULE_1_TIME_LIMIT = _("Limited by Schedule 1")
        SCHEDULE_1_ENERGY_LIMIT = _("Limited by Schedule 1 Energy")
        SCHEDULE_2_TIME_LIMIT = _("Limited by Schedule 2")
        SCHEDULE_2_ENERGY_LIMIT = _("Limited by Schedule 2 Energy")
        EXTERNAL_LIMIT = _("External Limit")

