"""End-to-end tests for device state read/write via real client connection.

Run with: pytest -m integration
Requires a live Grizzl-E device at the configured host.
"""

from __future__ import annotations

import pytest

from grizzl_e_local.client.versions import Version_01 as Client

pytestmark = pytest.mark.integration  # type: ignore[assignment]


def _value_within(original: int, ceiling: int) -> int:
    """Return a value within ``[0, ceiling]`` that differs from *original*.

    Prefers ``min(original + 10, ceiling)``; falls back to
    ``max(0, original - 5) or 5`` when the candidate equals *original*.
    """
    value = min(original + 10, ceiling)
    if value == original:
        value = max(0, original - 5) or 5
    return value


class TestReadNestedState:
    """Verify reading deeply nested component values."""

    @pytest.mark.asyncio
    async def test_reads_current_limit_value(self, client: Client):
        value = client.device.schedules[0].current_limit.value
        assert isinstance(value, int)

    @pytest.mark.asyncio
    async def test_reads_device_current_limit(self, client: Client):
        value = client.device.current_limit
        assert isinstance(value, int)

    @pytest.mark.asyncio
    async def test_reads_schedules_indexing(self, client: Client):
        schedule = client.device.schedules[0]
        assert hasattr(schedule, "is_enabled")


class TestAssignmentWrites:
    """Write via attribute assignment inside a transaction."""

    @pytest.mark.asyncio
    async def test_assignment_writes_are_refreshed(self, client: Client):
        original_value = client.device.schedules[0].current_limit.value
        device_limit = client.device.current_limit
        try:
            new_value = _value_within(original_value, device_limit)
            async with client.transaction(refresh=True):
                client.device.schedules[0].current_limit.value = new_value

            assert client.device.schedules[0].current_limit.value == new_value
        finally:
            async with client.transaction(refresh=True):
                client.device.schedules[0].current_limit.value = original_value


class TestFunctionStyleWrites:
    """Write via .set() inside a transaction."""

    @pytest.mark.asyncio
    async def test_set_writes_are_refreshed(self, client: Client):
        original_value = client.device.schedules[0].current_limit.value
        device_limit = client.device.current_limit
        try:
            new_value = _value_within(original_value, device_limit)
            async with client.transaction(refresh=True):
                await client.device.schedules[0].current_limit.set("value", new_value)

            assert client.device.schedules[0].current_limit.value == new_value
        finally:
            async with client.transaction(refresh=True):
                await client.device.schedules[0].current_limit.set("value", original_value)


class TestTransactionReset:
    """Verify values can be reset to originals after modifications."""

    @pytest.mark.asyncio
    async def test_reset_after_assignment(self, client: Client):
        original_value = client.device.schedules[0].current_limit.value
        device_limit = client.device.current_limit
        try:
            new_value = _value_within(original_value, device_limit)
            async with client.transaction(refresh=True):
                client.device.schedules[0].current_limit.value = new_value

            assert client.device.schedules[0].current_limit.value == new_value
        finally:
            async with client.transaction(refresh=True):
                client.device.schedules[0].current_limit.value = original_value
            # Verify reset
            assert client.device.schedules[0].current_limit.value == original_value


class TestTransactionWithRefreshTrue:
    """Verify refresh=True fetches updated state from device."""

    @pytest.mark.asyncio
    async def test_refresh_true_gets_latest(self, client: Client):
        original = client.device.current_limit
        cur_design = client.document.curDesign
        try:
            new_val = _value_within(original, cur_design)
            async with client.transaction(refresh=True):
                client.device.current_limit = new_val

            # After transaction exits, device state should reflect the write
            assert client.device.current_limit == new_val
        finally:
            async with client.transaction(refresh=True):
                client.device.current_limit = original


class TestTransactionWithoutRefresh:
    """Verify writes still work without refresh (uses local cache)."""

    @pytest.mark.asyncio
    async def test_write_without_refresh(self, client: Client):
        original_value = client.device.schedules[0].current_limit.value
        device_limit = client.device.current_limit
        try:
            new_value = _value_within(original_value, device_limit)
            async with client.transaction():
                await client.device.schedules[0].current_limit.set("value", new_value)

            assert client.device.schedules[0].current_limit.value == new_value
        finally:
            async with client.transaction(refresh=True):
                await client.device.schedules[0].current_limit.set("value", original_value)
