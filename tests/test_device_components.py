"""Tests for device component access and mutation patterns.

Covers lazy attribute delegation through State (sync __getattr__/__setattr__)
and async get/set methods for reading/writing component state without
requiring a transaction context or prior document cache.
"""
from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from grizzl_e_local.device.base import (
    BaseDevice,
    DeviceAttribute,
    MutableDeviceComponent,
    Node,
)
from grizzl_e_local.device.components import (
    MutableBool,
    MutableCurrency,
    MutableTimeDelta,
    MutableTimeRange,
    currency_to_int,
    to_currency,
)
from grizzl_e_local.context import transaction_batch
from grizzl_e_local.types import TimeRange


class _ImmutableState:
    pass


class _MutableState:
    def __init__(self, value: str = "default"):
        self.value = value


def _make_node_with_lazy_attrs():
    """Create a BaseDevice with lazy attributes that gets LazyAttrState."""

    class NetworkComp(MutableDeviceComponent[_MutableState]):
        attr_name = "network"
        state_factory = _MutableState
        field_args = ("ssidName",)

        def get_state_args(self):
            return (), {}

    class LimitsComp(Node, _ImmutableState):
        """A non-mutable component (no MutableDeviceComponent)."""

        def __init__(self, client, dependencies, /):
            self.client = client
            self.dependencies = dependencies
            self._state: list = []
            self._exceptions: list = []

    class MockClient:
        document = None
        get_document = AsyncMock()
        set_many = AsyncMock()

    client = MockClient()
    graph_mock = MagicMock()

    # Pre-create components so getattr(node, "_xxx") works
    network_state = _MutableState("mywifi")
    net_comp = NetworkComp(client, graph_mock, "ssidName")
    net_comp._state = network_state

    limits_comp = LimitsComp(client, graph_mock)

    class TestNode(BaseDevice):
        network_comp = DeviceAttribute(NetworkComp, "ssidName")
        limits_comp = DeviceAttribute(LimitsComp)

    node = TestNode(client, graph_mock)
    setattr(node, "_network_comp", net_comp)
    setattr(node, "_limits_comp", limits_comp)
    return node


class TestComponentGet:
    @pytest.mark.asyncio
    async def test_fetches_document_before_access(self):
        node = _make_node_with_lazy_attrs()
        state = type(node).state_factory(node)

        result = await state.get("network_comp")
        assert isinstance(result, _MutableState)
        assert result.value == "mywifi"
        node.client.get_document.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_state_via_descriptor(self):
        """get returns the descriptor's value (state), not the Node."""
        node = _make_node_with_lazy_attrs()
        state = type(node).state_factory(node)

        result = await state.get("network_comp")
        assert isinstance(result, _MutableState)
        # Not a DeviceComponent/Node instance
        assert not hasattr(result, "set_state_async")

    @pytest.mark.asyncio
    async def test_raises_attribute_error_for_invalid_name(self):
        node = _make_node_with_lazy_attrs()
        state = type(node).state_factory(node)

        with pytest.raises(AttributeError, match="bogus"):
            await state.get("bogus")


class TestComponentSet:
    @pytest.mark.asyncio
    async def test_sets_state_and_submits_fields(self):
        node = _make_node_with_lazy_attrs()
        state = type(node).state_factory(node)

        new_value = _MutableState("newwifi")
        await state.set("network_comp", new_value)

        assert node._network_comp.state.value == "newwifi"
        node.client.set_many.assert_awaited_once_with(ssidName=new_value)

    @pytest.mark.asyncio
    async def test_raises_for_non_lazy_attr(self):
        node = _make_node_with_lazy_attrs()
        state = type(node).state_factory(node)

        with pytest.raises(AttributeError, match="bogus"):
            await state.set("bogus", "x")

    @pytest.mark.asyncio
    async def test_raises_type_error_for_immutable_component(self):
        node = _make_node_with_lazy_attrs()
        state = type(node).state_factory(node)

        with pytest.raises(TypeError, match="is not a mutable component"):
            await state.set("limits_comp", "something")


class _RawDocument:
    """Document mock exposing raw device values via attribute access."""

    def __init__(self, data: dict):
        self._data = data

    def __getattr__(self, name: str):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name) from None


class TestComponentConversion:
    def test_bool_decodes_and_encodes_zero_one(self):
        client = MagicMock(document=_RawDocument({"sh1Enabled": 1}))
        node = MutableBool(client, MagicMock(), "sh1Enabled")
        assert node._state is True

        node._state = False
        assert node.to_fields() == {"sh1Enabled": 0}

    def test_currency_decodes_smallest_units_and_round_trips(self):
        client = MagicMock(document=_RawDocument({"moneyLimit": 36}))
        node = MutableCurrency(client, MagicMock(), "moneyLimit")
        assert node._state == to_currency(36)
        assert currency_to_int(node._state) == 36

    def test_timedelta_seconds_decode_and_encode(self):
        client = MagicMock(document=_RawDocument({"timeLimit": 7200}))
        node = MutableTimeDelta(client, MagicMock(), seconds="timeLimit")
        assert node._state == timedelta(hours=2)

        node._state = timedelta(seconds=95)
        assert node.to_fields() == {"timeLimit": 95}

    def test_time_range_minutes_round_trip(self):
        client = MagicMock(document=_RawDocument({"sh1Start": 960, "sh1Stop": 1200}))
        node = MutableTimeRange(client, MagicMock(), lower="sh1Start", upper="sh1Stop")
        assert node._state == TimeRange(time(16), time(20))

        assert node.to_fields() == {"sh1Start": 960, "sh1Stop": 1200}

    def test_system_time_round_trip(self):
        from grizzl_e_local.device.versions import SystemTime

        client = MagicMock(document=_RawDocument({"systemTime": 1750000000, "timeZone": -5}))
        node = SystemTime(client, MagicMock(), hours="systemTime", offset_hours="timeZone")
        expected = datetime.fromtimestamp(1750000000).astimezone(timezone(timedelta(hours=-5)))
        assert node._state == expected

        assert node.to_fields() == {"systemTime": 1750000000, "timeZone": -5}


class TestLazyAttrStateGetSetattr:
    def test_getattr_delegates_to_node(self):
        node = _make_node_with_lazy_attrs()
        state = type(node).state_factory(node)

        # Accessing a lazy attr via state delegates to the node's descriptor
        result = getattr(state, "network_comp")
        assert isinstance(result, _MutableState)
        assert result.value == "mywifi"

    def test_getattr_raises_for_non_lazy_attr(self):
        node = _make_node_with_lazy_attrs()
        state = type(node).state_factory(node)

        with pytest.raises(AttributeError):
            getattr(state, "bogus")

    @pytest.mark.asyncio
    async def test_setattr_delegates_to_node(self):
        """Setting a lazy attr via state delegates to the node's descriptor."""
        node = _make_node_with_lazy_attrs()
        state = type(node).state_factory(node)

        batch: dict[str, object] = {}
        token = transaction_batch.set(batch)
        try:
            new_value = _MutableState("via_state")
            state.network_comp = new_value  # triggers __setattr__ → descriptor.__set__
            assert node._network_comp.state.value == "via_state"
            assert batch == {"ssidName": new_value}
        finally:
            transaction_batch.reset(token)

    @pytest.mark.asyncio
    async def test_setattr_raises_type_error_for_immutable(self):
        """Setting an immutable component raises TypeError."""
        node = _make_node_with_lazy_attrs()
        state = type(node).state_factory(node)

        with pytest.raises(TypeError, match="is not a mutable component"):
            state.limits_comp = "something"
