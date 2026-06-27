from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import contextmanager
from functools import partial
from typing import TYPE_CHECKING, Any, overload

from ..util import flatten_exceptions
from .graph import DependencyGraph

if TYPE_CHECKING:
    from ..client import Client

logger = logging.getLogger(__name__)


class ComponentStateError(Exception):
    pass


class LazyAttrsClass(type):
    _lazy_attrs: set[str]

    def __new__(cls, name, bases, namespace: dict[str, Any], **kwargs):
        namespace.setdefault("_lazy_attrs", set())
        return super().__new__(cls, name, bases, namespace, **kwargs)


class NodeBase(LazyAttrsClass):
    state_factory: Callable[["NodeBase"], Any]
    get_state_args: Callable[["NodeBase"], tuple[tuple, dict[str, Any]]]

    def __new__(cls, name, bases, namespace: dict[str, Any], **kwargs):
        new_class = super().__new__(cls, name, bases, namespace, **kwargs)
        lazy_attrs = namespace["_lazy_attrs"]

        for base in new_class.__mro__:
            if isinstance(base, LazyAttrsClass):
                lazy_attrs |= base._lazy_attrs

        if not hasattr(new_class, "state_factory") and lazy_attrs:

            class Component:
                def __init__(self, node: NodeBase, *args, **kwargs):
                    self.node = node

                def __getattr__(self, name: str) -> Any:
                    if name in lazy_attrs:
                        return getattr(self.node, name)
                    raise AttributeError

                def __setattr__(self, name: str, value) -> None:
                    if name in lazy_attrs:
                        return setattr(self.node, name, value)
                    return super().__setattr__(name, value)

            Component.__name__ = name + 'Component'
            new_class.state_factory = Component

            if 'get_state_args' not in namespace:
                def get_state_args(self):
                    args, kwargs = super(new_class, self).get_state_args()  # type: ignore
                    if args:
                        if args[0] is not self:
                            args = (self, *args)
                    else:
                        args = (self,)
                    return args, kwargs

                new_class.get_state_args = get_state_args

        return new_class


class Node[T](metaclass=NodeBase):
    _exceptions: list[ComponentStateError]
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
    def exceptions(self) -> list[ComponentStateError]:
        return self._exceptions

    @property
    def in_exception_state(self) -> bool:
        return len(self._exceptions) > 0

    @contextmanager
    def exception_state(self, /, add=False):
        exceptions: list[ComponentStateError] = []
        if not add:
            self._exceptions = exceptions
        try:
            yield exceptions
        except* ComponentStateError as eg:
            exceptions.extend(flatten_exceptions(eg))
        finally:
            if add:
                self._exceptions.extend(exceptions)
            if self.in_exception_state:
                logger.warning("%r in exception state: %s", self, self._exceptions)

    def get_state_factory(self) -> Callable[..., T]:
        return self.state_factory

    def get_state(self) -> T:
        args, kwargs = self.get_state_args()
        return self._state_factory(*args, **kwargs or {})

    def get_state_args(self) -> tuple[tuple, dict[str, Any] | None]:
        args = tuple(self.get_field_value(f) for f in self.field_args)
        kwargs = {k: self.get_field_value(v) for k, v in self.field_kwargs.items()}
        return args, kwargs

    def get_field_value(self, field: str) -> Any:
        return getattr(self.client.document, field)

    def on_fields_changed(self, changed_fields: set[str]) -> None:
        raise NotImplementedError

    def change_fields(self, fields: dict[str, Any] | None = None) -> None:
        raise NotImplementedError


class BaseDevice(Node):
    attr_name = 'device'

    def on_fields_changed(self, changed_fields: set[str]) -> None:
        for node in self.dependencies:
            if fields := node.fields & changed_fields:
                node.on_fields_changed(fields)

    def change_fields(self, fields: dict[str, Any] | None = None) -> None:
        if fields:
            async def set_fields(fields: dict[str, Any]):
                await self.client.set_many(**fields)
                await self.client.get_document()

            task = asyncio.create_task(set_fields(fields))
            # task.add_done_callback  # TODO:


class DeviceComponent[T](Node[T]):

    def on_fields_changed(self, changed_fields: set[str]) -> None:
        # TODO: Potentially validate value or values from self.client.document and update
        # component state. The document is valid. Any validation is specific to the component:
        # (invalid means "in exception state"). Since this method is called in reaction to the
        # client fetch, it should not raise exceptions.
        pass

    def change_fields(self, fields: dict[str, Any] | None = None) -> None:
        # TODO: Turn component state into document field value and pass the field or fields down
        # the dependency chain, ultimately to the device which will call client.set_many with the
        # fields. Any dependency in the graph should be able to mutate the fields dict to change
        # the values that will be sent via the client.
        pass


class MutableDeviceComponent[T](DeviceComponent[T]):
    @DeviceComponent[T].state.setter
    def state(self, value: T) -> None:
        self._state = value


def component_from_type[T](wrapped: type[T], component_class: type[DeviceComponent[T]]):
    return type(
        wrapped.__name__ + 'Component',
        (component_class,),
        {'state_factory': wrapped}
    )

Mutable = partial(component_from_type, component_class=MutableDeviceComponent)


class DeviceComponentMixin(metaclass=LazyAttrsClass):
    pass


class DeviceAttribute:
    """Descriptor for lazy-initializing component state instances on Device."""

    attr_name: str
    component_class = DeviceComponent

    def __init__(
        self,
        type_or_path: type[Any] | str,
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
    def __get__(self, obj: Node, objtype: type) -> Any: ...

    def __get__(
        self, obj: Node | None, objtype: type | None = None
    ) -> Node | DeviceAttribute:
        if obj is None:
            return self
        try:
            attr = getattr(obj, self.attr_name)
        except AttributeError:
            attr = self.initialize(obj)
        assert isinstance(attr, Node)
        return attr.state

    def __set__(self, obj: Node, value: Any) -> None:
        try:
            attr = getattr(obj, self.attr_name)
        except AttributeError:
            attr = self.initialize(obj)
        assert isinstance(attr, Node)
        attr.state = value

    def __delete__(self, obj: Node) -> None:
        try:
            attr = getattr(obj, self.attr_name)
            obj.dependencies.remove(attr, obj)
        finally:
            delattr(obj, self.attr_name)

    def initialize(self, obj: Node) -> Node:
        if isinstance(self.lookup, str):
            path = self.lookup.split('.')
            state = obj.client.device
            for part in path:
                state = getattr(state, part)
            attr = obj.dependencies.ascend(['device'] + path)
        else:
            attr = self.lookup(
                obj.client,
                obj.dependencies,
                *self.field_args,
                **self.field_kwargs,
            )
            attr.attr_name = self.attr_name[1:]
        obj.dependencies.add(attr, obj)
        setattr(obj, self.attr_name, attr)
        return attr
