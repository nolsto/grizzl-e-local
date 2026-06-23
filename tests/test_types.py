from datetime import time

import pytest

from grizzl_e.types import TimeRange


class TestTimeRangeBasic:
    def test_disabled_range(self):
        tr = TimeRange(time(12, 0), time(12, 0))
        assert tr.is_disabled
        assert not tr.is_always_active

    def test_always_active_range(self):
        tr = TimeRange(time.min, time.max)
        assert not tr.is_disabled
        assert tr.is_always_active

    def test_normal_range(self):
        tr = TimeRange(time(9, 0), time(17, 0))
        assert not tr.is_disabled
        assert not tr.is_always_active

    def test_contains_time_in_range(self):
        tr = TimeRange(time(9, 0), time(17, 0))
        assert time(12, 0) in tr
        assert time(9, 0) in tr
        assert time(16, 59) in tr

    def test_contains_time_outside_range(self):
        tr = TimeRange(time(9, 0), time(17, 0))
        assert time(8, 59) not in tr
        assert time(17, 0) not in tr  # half-open: upper is excluded

    def test_contains_disabled_range(self):
        tr = TimeRange(time(12, 0), time(12, 0))
        assert time(12, 0) not in tr

    def test_midnight_wraparound(self):
        tr = TimeRange(time(22, 0), time(6, 0))
        assert time(23, 0) in tr
        assert time(0, 0) in tr
        assert time(5, 0) in tr
        assert time(6, 0) not in tr
        assert time(12, 0) not in tr


class TestTimeRangeIntervals:
    def test_normal_intervals(self):
        tr = TimeRange(time(9, 0), time(17, 0))
        assert tr._to_intervals() == [(540, 1020)]

    def test_midnight_wrap_intervals(self):
        tr = TimeRange(time(22, 0), time(6, 0))
        assert tr._to_intervals() == [(1320, 1440), (0, 360)]

    def test_disabled_intervals(self):
        tr = TimeRange(time(12, 0), time(12, 0))
        assert tr._to_intervals() == []


class TestTimeRangeOverlap:
    def test_no_overlap(self):
        a = TimeRange(time(9, 0), time(12, 0))
        b = TimeRange(time(14, 0), time(17, 0))
        assert not a.overlaps(b)

    def test_partial_overlap(self):
        a = TimeRange(time(9, 0), time(12, 0))
        b = TimeRange(time(11, 0), time(14, 0))
        assert a.overlaps(b)

    def test_exact_boundary_no_overlap(self):
        a = TimeRange(time(9, 0), time(12, 0))
        b = TimeRange(time(12, 0), time(14, 0))
        assert not a.overlaps(b)  # half-open intervals

    def test_full_overlap(self):
        a = TimeRange(time(9, 0), time(17, 0))
        b = TimeRange(time(10, 0), time(16, 0))
        assert a.overlaps(b)

    def test_midnight_wrap_overlap(self):
        a = TimeRange(time(22, 0), time(6, 0))
        b = TimeRange(time(3, 0), time(8, 0))
        assert a.overlaps(b)

    def test_disabled_no_overlap(self):
        a = TimeRange(time(12, 0), time(12, 0))
        b = TimeRange(time(9, 0), time(17, 0))
        assert not a.overlaps(b)

    def test_both_disabled_no_overlap(self):
        a = TimeRange(time(12, 0), time(12, 0))
        b = TimeRange(time(15, 0), time(15, 0))
        assert not a.overlaps(b)


class TestTimeRangeIntersection:
    def test_partial_intersection(self):
        a = TimeRange(time(9, 0), time(12, 0))
        b = TimeRange(time(11, 0), time(14, 0))
        result = a.intersection(b)
        assert result is not None
        assert result.lower == time(11, 0)
        assert result.upper == time(12, 0)

    def test_no_intersection(self):
        a = TimeRange(time(9, 0), time(12, 0))
        b = TimeRange(time(14, 0), time(17, 0))
        assert a.intersection(b) is None

    def test_midnight_wrap_intersection(self):
        a = TimeRange(time(22, 0), time(6, 0))
        b = TimeRange(time(3, 0), time(8, 0))
        result = a.intersection(b)
        assert result is not None
        assert result.lower == time(3, 0)
        assert result.upper == time(6, 0)

    def test_disabled_intersection(self):
        a = TimeRange(time(12, 0), time(12, 0))
        b = TimeRange(time(9, 0), time(17, 0))
        assert a.intersection(b) is None


class TestTimeRangeEquality:
    def test_equal_ranges(self):
        a = TimeRange(time(9, 0), time(17, 0))
        b = TimeRange(time(9, 0), time(17, 0))
        assert a == b

    def test_different_ranges(self):
        a = TimeRange(time(9, 0), time(17, 0))
        b = TimeRange(time(10, 0), time(17, 0))
        assert a != b

    def test_hashable(self):
        a = TimeRange(time(9, 0), time(17, 0))
        b = TimeRange(time(9, 0), time(17, 0))
        assert hash(a) == hash(b)
        s = {a, b}
        assert len(s) == 1
