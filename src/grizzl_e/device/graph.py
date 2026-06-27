from __future__ import annotations

from collections.abc import Iterable
from contextlib import suppress
from functools import cached_property, reduce
from typing import Generic, Protocol, TypeVar
from weakref import WeakKeyDictionary, WeakSet


class NamedAttr(Protocol):
    attr_name: str


T = TypeVar("T", bound=NamedAttr)


class DependencyGraph(Generic[T]):
    nodes: WeakKeyDictionary[T, WeakSet[T]]

    def __init__(self):
        self.nodes = WeakKeyDictionary()

    def __iter__(self):
        yield from self.sorted

    def __reversed__(self):
        return reversed(self.sorted)

    @cached_property
    def sorted(self) -> list[T]:
        "Topological sort from least depended on to most"

        if not self.nodes:
            return []

        # Nodes dependent on others. Each occurrence originates from a distinct dependency.
        dependents: list[T] = reduce(lambda x, y: [*x, *y], self.nodes.values(), [])
        # Nodes not dependent on any others
        nodes = set(self.nodes.keys()).difference(dependents)

        result: list[T] = []

        while nodes:
            node = nodes.pop()
            result.append(node)

            if not dependents:
                if result.count(node) > 1:
                    raise RuntimeError(
                        f"{self} requires all nodes to be dependent a single root node"
                    )
                break
            for dep in self.nodes[node]:
                dependents.remove(dep)
                if dep not in dependents:
                    nodes.add(dep)

        if len(result) != len(self.nodes):
            raise RuntimeError(f"{self} contains a cyclic dependency")

        return result

    @cached_property
    def inverted(self) -> WeakKeyDictionary[T, WeakSet[T]]:
        result = WeakKeyDictionary[T, WeakSet[T]]()

        for node, dependents in self.nodes.items():
            for dep in dependents:
                if dep not in result:
                    result[dep] = WeakSet()
                result[dep].add(node)

        return result

    def _invalidate_cache(self) -> None:
        with suppress(AttributeError):
            del self.sorted
        with suppress(AttributeError):
            del self.inverted

    def add(self, a: T, b: T) -> None:
        "Add dependency. A depends on B"

        if b not in self.nodes:
            self.nodes[b] = WeakSet()
        if a not in self.nodes:
            self.nodes[a] = WeakSet()
        self.nodes[a].add(b)
        self._invalidate_cache()

    def remove(self, a: T, b: T) -> None:
        "Remove dependency. A no longer depends on B"

        if a in self.nodes and b in self.nodes[a]:
            self.nodes[a].remove(b)
            self._invalidate_cache()

    def ascend(self, path: Iterable[str]) -> T:
        "Traverse dependencies from root node"

        path = list(path)
        if not path:
            raise ValueError
        base, *path = path

        result = self.sorted[-1]
        if base != result.attr_name:
            raise ValueError

        while path:
            part = path.pop(0)
            for node in self.inverted[result]:
                if node.attr_name == part:
                    result = node
                    break
            else:
                raise ValueError

        return result
