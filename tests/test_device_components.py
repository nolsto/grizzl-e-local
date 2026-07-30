"""Tests for device component access and mutation patterns.

Covers lazy attribute delegation through State (sync __getattr__/__setattr__)
and async get/set methods for reading/writing component state without
requiring a transaction context or prior document cache.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from grizzl_e_local.device.base import (
    BaseDevice,
    DeviceAttribute,
    MutableDeviceComponent,
    Node,
)
from grizzl_e_local.context import transaction_batch


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
