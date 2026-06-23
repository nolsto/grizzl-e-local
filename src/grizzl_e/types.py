from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from decimal import Decimal


def _time_to_minutes(t: time) -> int:
    """Convert a time to minutes from midnight."""
    return t.hour * 60 + t.minute


def _minutes_to_time(m: int) -> time:
    """Convert minutes from midnight to a time object."""
    return time(hour=m // 60, minute=m % 60)


class TimeRange:
    """A time-of-day range, supporting midnight wraparound.

    The range is half-open: [lower, upper).
    When lower == upper, the range is disabled (empty).
    When lower is time.min and upper is time.max, the range is always active.
    """

    __slots__ = ("lower", "upper")

    def __init__(self, lower: time, upper: time) -> None:
        self.lower = lower
        self.upper = upper

    @property
    def is_disabled(self) -> bool:
        return self.lower == self.upper

    @property
    def is_always_active(self) -> bool:
        return self.lower == time.min and self.upper == time.max

    def _to_intervals(self) -> list[tuple[int, int]]:
        """Convert to a list of (start_minutes, end_minutes) intervals.

        A range crossing midnight (e.g. 22:00-06:00) becomes two intervals.
        A disabled range (lower == upper) returns an empty list.
        """
        if self.is_disabled:
            return []

        lower = _time_to_minutes(self.lower)
        upper = _time_to_minutes(self.upper)

        if lower == upper:
            return []
        if lower < upper:
            return [(lower, upper)]
        # Wraps midnight
        return [(lower, 1440), (0, upper)]

    def __contains__(self, t: time) -> bool:
        if self.is_disabled:
            return False
        t_minutes = _time_to_minutes(t)
        for start, end in self._to_intervals():
            if start <= t_minutes < end:
                return True
        return False

    def overlaps(self, other: TimeRange) -> bool:
        """Check if this range overlaps with another."""
        if self.is_disabled or other.is_disabled:
            return False
        for s_start, s_end in self._to_intervals():
            for o_start, o_end in other._to_intervals():
                if s_start < o_end and o_start < s_end:
                    return True
        return False

    def intersection(self, other: TimeRange) -> TimeRange | None:
        """Return the overlapping period, or None if no overlap."""
        if not self.overlaps(other):
            return None

        best_start = 0
        best_end = 1440

        for s_start, s_end in self._to_intervals():
            for o_start, o_end in other._to_intervals():
                if s_start < o_end and o_start < s_end:
                    best_start = max(best_start, max(s_start, o_start))
                    best_end = min(best_end, min(s_end, o_end))

        return TimeRange(_minutes_to_time(best_start), _minutes_to_time(best_end))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.lower!r}, {self.upper!r})"

    def __str__(self) -> str:
        if self.is_disabled:
            return "disabled"
        return f"{self.lower.strftime('%H:%M')}-{self.upper.strftime('%H:%M')}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TimeRange):
            return NotImplemented
        return self.lower == other.lower and self.upper == other.upper

    def __hash__(self) -> int:
        return hash((self.lower, self.upper))


@dataclass(frozen=True)
class Rate:
    name: str
    value: Decimal
    time_range: TimeRange


@dataclass(frozen=True)
class Conflict:
    rates: tuple[str, str]
    overlap: TimeRange
    message: str
