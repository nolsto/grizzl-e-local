from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import contextmanager
from functools import partial
from typing import TYPE_CHECKING, Any, Protocol, cast, overload

from ..util import flatten_exceptions
from ..context import transaction_batch
from .graph import NamedAttrDependencyGraph as DependencyGraph

if TYPE_CHECKING:
    from ..client import Client

logger = logging.getLogger(__name__)


class StateError(Exception):
    pass


class State[T: Node]:
    _node: T

    def __init__(self, node: T, /, *args, **kwargs):
        self._node = node


class LazyAttrState[T: Node](State[T]):
    """Base State for Node with lazy attributes.

    Delegates attribute reads and writes to the Node. Provides async methods
    for reading/writing component state without requiring a transaction context
    or prior document cache.
    """
    _lazy_attrs: set[str]

    def __getattr__(self, name: str) -> Any:
        if name in self._lazy_attrs:
            try:
                return getattr(self._node, name)
            except Exception as e:
                raise AttributeError from e
        raise AttributeError

    def __setattr__(self, name: str, value) -> None:
        if name in self._lazy_attrs:
            try:
                return setattr(self._node, name, value)
            except NotImplementedError:
                raise TypeError(
                    f"{type(self).__name__}.{name} is not a mutable component"
                ) from None
        super().__setattr__(name, value)

    async def get(self, attr_name: str) -> Any:
        """Get the state of a component node (fetching document if needed)."""
        if attr_name not in self._lazy_attrs:
            raise AttributeError(attr_name)
        await self._node.client.get_document()
        return getattr(self._node, attr_name)

    async def set(self, attr_name: str, value: Any) -> None:
        """Set a component's state and submit fields directly to the client."""
        await self.get(attr_name)  # Create the component if it has not yet been created
        # Avoid setting the state through the descriptor as this follows the sync set_state path.
        comp = getattr(self._node, f"_{attr_name}")
        if not isinstance(comp, MutableDeviceComponent):
            raise TypeError(
                f"{type(self).__name__}.{attr_name} is not a mutable component"
            ) from None
        await comp.set_state_async(value)


class LazyAttrsClass(type):
    _lazy_attrs: set[str]

    def __new__(cls, name, bases, namespace: dict[str, Any], **kwargs):
        namespace.setdefault("_lazy_attrs", set())
        return super().__new__(cls, name, bases, namespace, **kwargs)


class NodeBase(LazyAttrsClass):
    state_factory: Callable[["NodeBase"], Any]
    get_state_args: Callable[["NodeBase"], tuple[tuple, dict[str, Any]]]

    def __new__(cls, name, bases, namespace: dict[str, Any], **kwargs):
        state_class: type | None = None
        if "State" in namespace and isinstance(namespace["State"], type):
            state_class = cast(type, namespace.pop("State"))
        if "state_factory" in namespace:
            if state_class:
                raise ValueError("State class and state_factory must not both be defined.")
            if isinstance(namespace["state_factory"], type):
                state_class = cast(type, namespace.pop("state_factory"))

        new_class = super().__new__(cls, name, bases, namespace, **kwargs)

        lazy_attrs = namespace["_lazy_attrs"]
        for base in new_class.__mro__:
            if isinstance(base, LazyAttrsClass):
                lazy_attrs |= base._lazy_attrs

        if not hasattr(new_class, "state_factory") and lazy_attrs:
            state_bases = (LazyAttrState,)
            if state_class:
                state_bases = (state_class, *state_bases)
            state_class = type(name + "State", state_bases, {"_lazy_attrs": lazy_attrs})

        if state_class:
            if issubclass(state_class, State) and 'get_state_args' not in namespace:
                def get_state_args(self):
                    # State requires first positional argument to be the Node instance.
                    args, kwargs = super(new_class, self).get_state_args()  # type: ignore
                    if args:
                        if args[0] is not self:
                            args = (self, *args)
                    else:
                        args = (self,)
                    return args, kwargs

                new_class.get_state_args = get_state_args

            new_class.state_factory = state_class

        return new_class


class Node[T](metaclass=NodeBase):
    _state: T
    _exceptions: list[StateError]
    field_args: tuple[str, ...]
    field_kwargs: dict[str, str]
    attr_name: str
    state_factory: Callable[..., T]

    def __init__(
        self,
        client: Client,
        dependencies: DependencyGraph[Node],
        /,
        *field_args: str,
        **field_kwargs: str,
    ) -> None:
        self.client = client
        self.dependencies = dependencies
        self.field_args = field_args
        self.field_kwargs = field_kwargs
        self._state_factory = self.get_state_factory()
        self._state = self.get_state()
        self._exceptions = []

    def __str__(self) -> str:
        result = f"[{self.__class__.__name__}.{self.attr_name}]"
        if self.fields:
            result += f" {self.fields}"
        return result

    @property
    def fields(self) -> set[str]:
        return {*self.field_args, *self.field_kwargs.keys()}

    @property
    def state(self) -> T:
        return self._state

    @state.setter
    def state(self, value: T) -> None:
        raise NotImplementedError

    @property
    def exceptions(self) -> list[StateError]:
        return self._exceptions

    @property
    def in_exception_state(self) -> bool:
        return len(self._exceptions) > 0

    @contextmanager
    def exception_state(self, /, add=False):
        prev_exception_state = self.in_exception_state
        exceptions: list[StateError] = []
        if not add:
            self._exceptions = exceptions
        try:
            yield exceptions
        except* StateError as eg:
            exceptions.extend(flatten_exceptions(eg))
        finally:
            if add:
                self._exceptions.extend(exceptions)
            if self.in_exception_state:
                logger.warning("%s in exception state: %s", self, self._exceptions)
            elif prev_exception_state:
                logger.info("%s no longer in exception state", self)


    def get_state_factory(self) -> Callable[..., T]:
        return self.state_factory

    def get_state_args(self) -> tuple[tuple, dict[str, Any] | None]:
        args = tuple(self.get_field_value(f) for f in self.field_args)
        kwargs = {k: self.get_field_value(v) for k, v in self.field_kwargs.items()}
        return args, kwargs

    def get_state(self) -> T:
        args, kwargs = self.get_state_args()
        return self._state_factory(*args, **kwargs or {})

    def validate_state(self) -> None:
        # Override to provide additional validation logic (beyond document field validation).
        # An invalid state should ensure `self.in_exception_state == True` at the end of this
        # method. Use `with self.exception_state():` to capture `StateError`s.
        pass

    def get_field_value(self, field: str) -> Any:
        return getattr(self.client.document, field)

    def on_fields_changed(self, changed_fields: set[str]) -> None:
        old_state = getattr(self, "_state", None)
        self._state = self.get_state()
        with self.exception_state():
            self.validate_state()
        if self._state != old_state:
            logger.info("%r state changed: %s -> %s", self, old_state, self._state)

    def set_fields(self, fields: dict[str, Any]) -> None:
        try:
            batch = transaction_batch.get()
        except LookupError:
            raise RuntimeError(
                f"{type(self).__name__} fields must be set inside a Client.transaction() context"
            )
        batch.update(fields)

    async def set_fields_async(self, fields: dict[str, Any]) -> None:
        """Set fields directly via the client (no transaction batching)."""
        await self.client.set_many(**fields)


class BaseDevice(Node):
    attr_name = 'device'


class DeviceComponent[T](Node[T]):
    pass


class MutableDeviceComponent[T](DeviceComponent[T]):
    """A DeviceComponent with a state that can be set"""

    @DeviceComponent[T].state.setter
    def state(self, value: T) -> None:
        self.set_state(value)

    def set_state(self, value: T) -> None:
        self._state = value
        self.set_fields(self.serialize())

    async def set_state_async(self, value: T) -> None:
        self._state = value
        await self.set_fields_async(self.serialize())

    def serialize(self, validate=True):
        data = self.to_fields()
        if not validate:
            return data

        errors: dict[Node, list[StateError]] = {}
        fields = set(data)
        for component in self.dependencies:
            if component.fields & fields:
                try:
                    component.validate_state()
                except* StateError as eg:
                    errors[component] = flatten_exceptions(eg)
        if errors:
            raise StateError(
                f"{self} failed validation with {len(errors)} error(s):\n"
                + "\n".join(
                    "{}: {}".format(comp, "\n".join(str(e) for e in errs))
                    for comp, errs in errors.items()
                )
            )
        return data

    def to_fields(self) -> dict[str, object]:
        """Serialize current state into document field:value pairs."""
        if len(self.field_args) == 1 and not self.field_kwargs:
            return {self.field_args[0]: self._state}
        raise NotImplementedError(
            f"{type(self).__name__} has multiple fields or complex mapping; "
            "override to_fields()"
        )


def component_from_type[T, N: Node](wrapped: type[T], component_class: type[N]) -> type[N]:
    return type(
        wrapped.__name__ + component_class.__name__,
        (component_class,),
        {'state_factory': wrapped}
    )

class _Mutable(Protocol):
    def __call__[T](self, t: type[T]) -> type[MutableDeviceComponent[T]]: ...

Mutable: _Mutable = partial(component_from_type, component_class=MutableDeviceComponent)
Mutable.__doc__ = "Use the given type as the state factory for a mutable device component"


class DeviceComponentMixin(metaclass=LazyAttrsClass):
    """A mixin to share methods and device attributes between device components"""
    pass


class DeviceAttribute[T]:
    """Descriptor for lazy-initializing component state instances on Device."""

    attr_name: str
    component_class = DeviceComponent

    def __init__(
        self,
        type_or_path: type[Node[T]] | type[T] | str,
        *field_args: str,
        **field_kwargs: str
    ) -> None:
        if isinstance(type_or_path, str):
            if field_args or field_kwargs:
                raise ValueError
        elif not issubclass(type_or_path, Node):
            type_or_path = component_from_type(type_or_path, self.component_class)

        self.lookup = type_or_path
        self.field_args = field_args
        self.field_kwargs = field_kwargs

    def __set_name__(self, owner: type[LazyAttrsClass], name: str) -> None:
        self.attr_name = f"_{name}"
        owner._lazy_attrs.add(name)

    @overload
    def __get__(self, obj: None, objtype: None) -> DeviceAttribute: ...

    @overload
    def __get__(self, obj: Node, objtype: type) -> T: ...

    def __get__(
        self, obj: Node | None, objtype: type | None = None
    ) -> T | DeviceAttribute:
        if obj is None:
            return self
        try:
            attr = getattr(obj, self.attr_name)
        except AttributeError:
            attr = self._create(obj)
        assert isinstance(attr, Node)
        return attr.state

    def __set__(self, obj: Node, value: Any) -> None:
        try:
            attr = getattr(obj, self.attr_name)
        except AttributeError:
            attr = self._create(obj)
        assert isinstance(attr, Node)
        attr.state = value

    def __delete__(self, obj: Node) -> None:
        try:
            attr = getattr(obj, self.attr_name)
            obj.dependencies.remove(attr, obj)
        finally:
            delattr(obj, self.attr_name)

    def _create(self, obj: Node) -> Node:
        if isinstance(self.lookup, str):
            path = self.lookup.split('.')
            state = obj.client.device
            for part in path:
                state = getattr(state, part)
            attr = obj.dependencies.ascend(['device'] + path)
            created = False
        else:
            attr = self.lookup(
                obj.client,
                obj.dependencies,
                *self.field_args,
                **self.field_kwargs,
            )
            attr.attr_name = self.attr_name[1:]  # Without leading underscore
            created = True

        obj.dependencies.add(attr, obj)
        setattr(obj, self.attr_name, attr)

        if created:
            with attr.exception_state():
                attr.validate_state()
        return attr
