from __future__ import annotations

import operator
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from functools import cached_property
from typing import Literal


@dataclass(repr=False, eq=False, frozen=True, slots=True)
class TimeRange:
    lower: time
    upper: time

    @property
    def upper_inc(self):
        return self.upper is time.max

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.lower!r}, {self.upper!r})"

    def __str__(self) -> str:
        upper_bound = "]" if self.upper_inc else ")"
        return f"[{self.lower}-{self.upper}{upper_bound}"

    def __hash__(self) -> int:
        return hash((self.lower, self.upper))

    def __contains__(self, other) -> bool:
        if isinstance(other, type(self)):
            return self & other == other
        if not isinstance(other, time):
            raise TypeError

        op = operator.le if self.upper_inc else operator.lt
        return other >= self.lower and op(other, self.upper)

    def __eq__(self, other) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.lower == other.lower and self.upper == other.upper

    def __and__(self, other) -> TimeRange | None:
        if not isinstance(other, type(self)):
            return NotImplemented

        if self.lower < other.upper and other.lower < self.upper:
            return self.__class__(
                max(self.lower, other.lower),
                min(self.upper, other.upper),
            )
        return None


@dataclass(repr=False, eq=False, frozen=True)
class WraparoundTimeRange:
    """A time-of-day range, supporting midnight wraparound."""

    lower: time | None = None
    upper: time | None = None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.lower!r}, {self.upper!r})"

    def __str__(self) -> str:
        return f"({self.lower or 'Unbound'}-{self.upper or 'Unbound'})"

    def __hash__(self) -> int:
        return hash((self.lower, self.upper))

    def __contains__(self, other) -> bool:
        if isinstance(other, type(self) | TimeRange):
            return self & other == other
        if not isinstance(other, time):
            raise TypeError
        return any(other in r for r in self.ranges)

    def __eq__(self, other) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.ranges == other.ranges

    def __and__(self, other) -> WraparoundTimeRange | None:
        if isinstance(other, type(self)):
            other = other.ranges
        elif isinstance(other, TimeRange):
            other = (other,)
        else:
            return NotImplemented

        lower: time | None = None
        upper: time | None = None

        for a in other:
            for b in self.ranges:
                intersection = a & b
                if intersection is None:
                    continue
                if lower is None:
                    lower = intersection.lower
                upper = intersection.upper

        if lower and upper:
            try:
                return self.__class__(
                    lower if lower != time.min else None,
                    upper if upper != time.max else None,
                )
            except ValueError:
                if lower != upper:
                    raise
        return None

    @cached_property
    def ranges(self) -> tuple[()] | tuple[TimeRange] | tuple[TimeRange, TimeRange]:
        lower = self.lower or time.min
        upper = self.upper or time.max

        if lower == upper:
            return ()
        elif lower < upper:
            return TimeRange(lower, upper),
        else:
            return TimeRange(lower, time.max), TimeRange(time.min, upper)

    def timedelta(
        self,
        resolution: Literal["hours", "minutes", "seconds", "milliseconds", "microseconds"] = "seconds"
    ) -> timedelta:
        d = date.today()
        td = timedelta(**{resolution: 1})
        return timedelta(**{
            resolution: sum(
                (datetime.combine(d, r.upper) - datetime.combine(d, r.lower)) // td
                for r in self.ranges
            )
        })
