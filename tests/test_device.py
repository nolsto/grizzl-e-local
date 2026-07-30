import logging
from unittest.mock import MagicMock

import pytest

from grizzl_e_local.device.base import (
    BaseDevice,
    DeviceAttribute,
    DeviceComponent,
    MutableDeviceComponent,
    NodeBase,
    StateError,
)
from grizzl_e_local.context import transaction_batch


class MockDocument:
    """Minimal document mock for node tests."""

    def __init__(self, data: dict | None = None):
        self._data = data or {}

    def __getattr__(self, name: str):
        if name in self._data:
            return self._data[name]
        raise AttributeError(name)


class MockClient:
    """Minimal client mock for node tests."""

    def __init__(self, document_data: dict | None = None):
        self.document = MockDocument(document_data)


class TestLazyAttrsClass:
    def test_collects_lazy_attrs_from_namespace(self):
        class _Test(metaclass=NodeBase):
            _lazy_attrs = {"a", "b"}

        assert _Test._lazy_attrs == {"a", "b"}

    def test_merges_lazy_attrs_from_bases(self):
        class Base(metaclass=NodeBase):
            _lazy_attrs = {"x"}

        class Child(Base, metaclass=NodeBase):
            _lazy_attrs = {"y"}

        assert Child._lazy_attrs == {"x", "y"}


class TestNodeBase:
    def test_rejects_both_state_class_and_factory(self):
        with pytest.raises(ValueError, match="must not both"):
            class BadClass(metaclass=NodeBase):
                State = object
                state_factory = lambda self: {}

    def test_state_class_becomes_factory(self):
        class State:
            pass

        ns = {"State": State, "__module__": __name__}
        cls = NodeBase("TestNode", (object,), ns)

        assert cls.state_factory is State

    def test_type_becomes_factory(self):
        class Factory:
            pass

        class TestNode(metaclass=NodeBase):
            state_factory = Factory

        assert TestNode.state_factory is Factory


class _SimpleState:
    def __init__(self, value: int):
        self.value = value


def _make_node(field_args=(), field_kwargs=None, doc_data=None):
    """Create a minimal Node subclass instance for testing."""
    if field_kwargs is None:
        field_kwargs = {}

    fa = tuple(field_args)
    fk = dict(field_kwargs)

    class TestNode(DeviceComponent[_SimpleState]):
        attr_name = "test"
        state_factory = _SimpleState
        field_args = fa
        field_kwargs = fk
        _exceptions: list = []  # workaround: Node doesn't init this

        def get_state_args(self):
            return (), {"value": 42}

    client = MockClient(doc_data)
    graph_mock = MagicMock()
    node = TestNode(client, graph_mock, *fa, **fk)
    return node


class TestNodeState:
    def test_get_state_calls_factory(self):
        node = _make_node()
        assert isinstance(node._state, _SimpleState)
        assert node._state.value == 42

    def test_state_property_returns_internal(self):
        node = _make_node()
        assert node.state is node._state


class TestNodeFields:
    def test_fields_includes_args_and_kwargs_keys(self):
        node = _make_node(
            field_args=("a", "b"),
            field_kwargs={"x": "y"},
        )
        assert node.fields == {"a", "b", "x"}

    def test_get_field_value_from_document(self):
        client = MockClient({"myField": 100})

        class TestNode(DeviceComponent[_SimpleState]):
            attr_name = "test"
            state_factory = _SimpleState
            field_args = ("myField",)

            def get_state_args(self):
                return (), {"value": 42}

        node = TestNode(client, MagicMock())
        assert node.get_field_value("myField") == 100


class TestNodeExceptionHandling:
    def test_initially_no_exceptions(self):
        node = _make_node()
        assert not node.in_exception_state
        assert node.exceptions == []

    def test_exception_state_captures_state_errors(self):
        from grizzl_e_local.device.base import StateError

        node = _make_node()

        with node.exception_state():
            raise StateError("state error 1")

        assert len(node.exceptions) >= 1


class _ValidatingState:
    """State that holds a value without domain validation."""

    def __init__(self, value: int):
        self.value = value


class _ValidatingNode(DeviceComponent[_ValidatingState]):
    """Node that validates state in validate_state()."""

    attr_name = "test"
    state_factory = _ValidatingState
    field_args = ("myField",)
    _exceptions: list = []  # workaround

    def validate_state(self) -> None:
        with self.exception_state():
            if self._state.value < 0 or self._state.value > 100:
                raise StateError(f"value {self._state.value} out of range [0, 100]")

    def get_state_args(self):
        return (), {"value": self.get_field_value("myField")}


class TestNodeExceptionState:
    def test_initial_state_clears_exceptions(self):
        node = _make_node()
        assert not node.in_exception_state
        assert node.exceptions == []

    def test_init_does_not_validate(self):
        client = MockClient({"myField": -1})
        node = _ValidatingNode(client, MagicMock())

        assert not node.in_exception_state
        assert node.exceptions == []
        assert hasattr(node, "_state")
        assert node._state.value == -1

    def test_init_valid_state_ok(self):
        client = MockClient({"myField": 42})
        node = _ValidatingNode(client, MagicMock())

        assert not node.in_exception_state
        assert node._state.value == 42

    def test_on_fields_changed_captures_validation_errors(self):
        client = MockClient({"myField": 50})
        node = _ValidatingNode(client, MagicMock())

        assert not node.in_exception_state
        assert node._state.value == 50

        client.document._data["myField"] = 200
        node.on_fields_changed({"myField"})

        assert node.in_exception_state
        assert len(node.exceptions) == 1
        assert node._state.value == 200  # state still assigned, just invalid

    def test_on_fields_changed_clears_exceptions_on_valid_update(self):
        client = MockClient({"myField": -1})
        node = _ValidatingNode(client, MagicMock())

        # Manually trigger validation to create exception state
        with node.exception_state():
            node.validate_state()
        assert node.in_exception_state
        assert len(node.exceptions) == 1

        client.document._data["myField"] = 50
        node.on_fields_changed({"myField"})

        # Valid update clears exceptions and sets new state
        assert not node.in_exception_state
        assert node.exceptions == []
        assert node._state.value == 50

    def test_on_fields_changed_logs_state_change(self, caplog):
        client = MockClient({"myField": 10})
        node = _ValidatingNode(client, MagicMock())
        client.document._data["myField"] = 20
        with caplog.at_level(logging.INFO):
            node.on_fields_changed({"myField"})

        assert "state changed:" in caplog.text

    def test_missing_field_propagates_not_caught(self):
        class _SimpleState:
            def __init__(self, value: int):
                self.value = value

        client = MockClient({"otherField": 42})

        class TestNode(DeviceComponent[_SimpleState]):
            attr_name = "test"
            state_factory = _SimpleState
            field_args = ("missingField",)
            _exceptions: list = []  # workaround

            def get_state_args(self):
                return (), {"value": self.get_field_value("missingField")}

        with pytest.raises(AttributeError):  # missing field propagates
            TestNode(client, MagicMock())


class TestNodeSetFields:
    def test_raises_outside_transaction(self):
        node = _make_node()
        with pytest.raises(RuntimeError, match="must be set inside"):
            node.set_fields({"a": 1})

    def test_accumulates_in_transaction(self):
        node = _make_node()
        batch: dict[str, object] = {}
        token = transaction_batch.set(batch)
        try:
            node.set_fields({"a": 1, "b": 2})
            assert batch == {"a": 1, "b": 2}
        finally:
            transaction_batch.reset(token)

    def test_overwrites_existing_keys(self):
        node = _make_node()
        batch: dict[str, object] = {}
        token = transaction_batch.set(batch)
        try:
            node.set_fields({"a": 1})
            node.set_fields({"a": 2})
            assert batch == {"a": 2}
        finally:
            transaction_batch.reset(token)


class _SingleFieldState:
    def __init__(self, value: str):
        self.value = value


def _make_mutable_node(field_args=(), field_kwargs=None, doc_data=None):
    if field_kwargs is None:
        field_kwargs = {}

    fa = tuple(field_args)
    fk = dict(field_kwargs)

    class TestNode(MutableDeviceComponent[_SingleFieldState]):
        attr_name = "test"
        state_factory = _SingleFieldState
        field_args = fa
        field_kwargs = fk

        def get_state_args(self):
            return (), {"value": "hello"}

    client = MockClient(doc_data)
    graph_mock = MagicMock()
    node = TestNode(client, graph_mock, *fa, **fk)
    return node


class TestMutableDeviceComponent:
    def test_set_state_updates_and_serializes(self):
        batch: dict[str, object] = {}
        token = transaction_batch.set(batch)
        try:
            node = _make_mutable_node(field_args=("myField",))
            assert node._state.value == "hello"

            new_state = _SingleFieldState("world")
            node.state = new_state
            assert node._state is new_state
            assert batch == {"myField": new_state}
        finally:
            transaction_batch.reset(token)

    def test_to_fields_single_field(self):
        node = _make_mutable_node(field_args=("myField",))
        result = node.to_fields()
        assert result["myField"] is node._state
        assert result["myField"].value == "hello"

    def test_to_fields_multi_field_raises(self):
        node = _make_mutable_node(
            field_args=("a", "b"),
            doc_data={"a": 1, "b": 2},
        )
        with pytest.raises(NotImplementedError, match="multiple fields"):
            node.to_fields()

    def test_to_fields_kwargs_raises(self):
        node = _make_mutable_node(
            field_kwargs={"x": "y"},
            doc_data={"x": 10},
        )
        with pytest.raises(NotImplementedError, match="complex mapping"):
            node.to_fields()


class _TestComponentState:
    def __init__(self):
        self.name = "default"


def _make_descriptor_test_class():
    """Create a test class with a DeviceAttribute descriptor."""
    class TestComponent(MutableDeviceComponent[_TestComponentState]):
        attr_name = "test_comp"
        state_factory = _TestComponentState
        field_args = ("compField",)

        def get_state_args(self):
            return (), {}

    class LazyOwner(metaclass=NodeBase):
        _lazy_attrs: set[str] = set()
        client_attr = DeviceAttribute(TestComponent, "compField")

    return LazyOwner


class TestDeviceAttributeDescriptor:
    def test_get_on_class_returns_descriptor(self):
        cls = _make_descriptor_test_class()
        result = getattr(cls, "client_attr")
        assert isinstance(result, DeviceAttribute)

    def test_set_name_registers_lazy_attrs(self):
        cls = _make_descriptor_test_class()
        assert "client_attr" in cls._lazy_attrs

    def test_get_on_instance_triggers_creation(self):
        cls = _make_descriptor_test_class()

        class MockOwner:
            client = MockClient({"compField": 1})
            dependencies = MagicMock()

        owner = MockOwner()
        desc = getattr(cls, "client_attr")

        # First access creates the component
        state = desc.__get__(owner, type(owner))
        assert isinstance(state, _TestComponentState)
        assert hasattr(owner, "_client_attr")

    def test_set_on_instance_delegates_to_state(self):
        cls = _make_descriptor_test_class()

        class MockOwner:
            client = MockClient({"compField": 1})
            dependencies = MagicMock()

        owner = MockOwner()
        desc = getattr(cls, "client_attr")
        desc.__get__(owner, type(owner))  # trigger creation

        batch: dict[str, object] = {}
        token = transaction_batch.set(batch)
        try:
            desc.__set__(owner, _TestComponentState())
            assert owner._client_attr.state.name == "default"
        finally:
            transaction_batch.reset(token)


class TestDeviceAttributePathResolution:
    def test_string_path_rejects_field_args(self):
        """String paths cannot have field_args or field_kwargs."""
        with pytest.raises(ValueError):
            DeviceAttribute("device.nested", "field")

        with pytest.raises(ValueError):
            DeviceAttribute("device.nested", x="y")


class TestBaseDevice:
    def test_has_device_attr_name(self):
        assert BaseDevice.attr_name == "device"
