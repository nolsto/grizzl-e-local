from datetime import time

import pytest

from grizzl_e.types import TimeRange, WraparoundTimeRange


class TestWraparoundTimeRangeBasic:
    def test_invalid_range(self):
        with pytest.RaisesExc(ValueError):
            WraparoundTimeRange(time(6, 0), time(6, 0))

    def test_unbound_range(self):
        tr = WraparoundTimeRange()
        assert time.min in tr
        assert time.max in tr

    def test_unbound_lower_range(self):
        tr = WraparoundTimeRange(upper=time(12, 0))
        assert time.min in tr

    def test_unbound_upper_range(self):
        tr = WraparoundTimeRange(lower=time(12, 0))
        assert time.max in tr

    def test_normal_range(self):
        tr = WraparoundTimeRange(time(9, 0), time(17, 0))
        assert time(9, 0) in tr
        assert time(16, 59) in tr

    def test_contains_time_outside_range(self):
        tr = WraparoundTimeRange(time(9, 0), time(17, 0))
        assert time(8, 59) not in tr
        assert time(17, 0) not in tr  # half-open: upper is excluded

    def test_midnight_wraparound(self):
        tr = WraparoundTimeRange(time(22, 0), time(6, 0))
        assert time(22, 0) in tr
        assert time(0, 0) in tr
        assert time(5, 59) in tr
        assert time(21, 59) not in tr
        assert time(6, 0) not in tr


class TestWraparoundTimeRangeEquality:
    def test_equal_ranges(self):
        a = WraparoundTimeRange(time(9, 0), time(17, 0))
        b = WraparoundTimeRange(time(9, 0), time(17, 0))
        assert a == b

    def test_different_ranges(self):
        a = WraparoundTimeRange(time(9, 0), time(17, 0))
        b = WraparoundTimeRange(time(10, 0), time(17, 0))
        assert a != b

    def test_hashable(self):
        a = WraparoundTimeRange(time(9, 0), time(17, 0))
        b = WraparoundTimeRange(time(9, 0), time(17, 0))
        assert hash(a) == hash(b)
        assert len({a, b}) == 1


class TestWraparoundTimeRangeIntervals:
    def test_normal_intervals(self):
        tr = WraparoundTimeRange(time(9, 0), time(17, 0))
        assert tr.ranges == (
            TimeRange(time(9, 0), time(17, 0)),
        )

    def test_midnight_wrap_intervals(self):
        tr = WraparoundTimeRange(time(22, 0), time(6, 0))
        assert tr.ranges == (
            TimeRange(time(22, 0), time.max),
            TimeRange(time.min, time(6, 0)),
        )


class TestWraparoundTimeRangeOverlap:
    def test_no_overlap(self):
        a = WraparoundTimeRange(time(9, 0), time(12, 0))
        b = WraparoundTimeRange(time(14, 0), time(17, 0))
        assert a & b is None

    def test_partial_overlap(self):
        a = WraparoundTimeRange(time(9, 0), time(12, 0))
        b = WraparoundTimeRange(time(11, 0), time(14, 0))
        assert a & b == WraparoundTimeRange(time(11, 0), time(12, 0))

    def test_exact_boundary_no_overlap(self):
        a = WraparoundTimeRange(time(9, 0), time(12, 0))
        b = WraparoundTimeRange(time(12, 0), time(14, 0))
        assert a & b is None  # half-open intervals

    def test_full_overlap(self):
        a = WraparoundTimeRange(time(9, 0), time(17, 0))
        b = WraparoundTimeRange(time(10, 0), time(16, 0))
        assert a & b == b
        assert b in a

    def test_exact_boundary_full_overlap(self):
        a = WraparoundTimeRange(time(9, 0), time(12, 0))
        b = WraparoundTimeRange(time(10, 0), time(12, 0))
        assert a & b == b
        assert b in a

    def test_midnight_wrap_partial_overlap(self):
        a = WraparoundTimeRange(time(22, 0), time(6, 0))
        b = WraparoundTimeRange(time(3, 0), time(8, 0))
        assert a & b == WraparoundTimeRange(time(3, 0), time(6, 0))

    def test_midnight_wrap_full_overlap(self):
        a = WraparoundTimeRange(time(22, 0), time(6, 0))
        b = WraparoundTimeRange(time(3, 0), time(6, 0))
        assert a & b == WraparoundTimeRange(time(3, 0), time(6, 0))
        assert b in a
