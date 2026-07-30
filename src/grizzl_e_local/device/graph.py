from __future__ import annotations

from collections.abc import Iterable
from contextlib import suppress
from functools import cached_property, reduce
from typing import Protocol
from weakref import WeakKeyDictionary, WeakSet


class DependencyGraph[T]:
    nodes: WeakKeyDictionary[T, WeakSet[T]]

    def __init__(self):
        self.nodes = WeakKeyDictionary()

    def __getitem__(self, node: T) -> WeakSet[T]:
        return self.nodes[node]

    def __iter__(self):
        yield from self.sorted

    def __reversed__(self):
        return reversed(self.sorted)

    @cached_property
    def sorted(self) -> list[T]:
        """Topological sort: dependencies appear after the nodes that depend on them."""

        if not self.nodes:
            return []

        # in-degree = number of dependencies each node has.
        in_degree: dict[T, int] = {node: len(deps) for node, deps in self.nodes.items()}

        # Start with nodes that have no dependencies (depend on nothing).
        queue: list[T] = [node for node, deg in in_degree.items() if deg == 0]
        result: list[T] = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            # For each node that depends on the current one, decrease its in-degree.
            for dependent in self.inverted.get(node, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self.nodes):
            raise RuntimeError(f"{self} contains a cyclic dependency")

        return list(reversed(result))

    @cached_property
    def inverted(self) -> WeakKeyDictionary[T, WeakSet[T]]:
        """Inverts the graph: node key maps to a set of nodes dependent on it"""

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
        """Add dependency. A depends on B"""

        if b not in self.nodes:
            self.nodes[b] = WeakSet()
        if a not in self.nodes:
            self.nodes[a] = WeakSet()
        self.nodes[a].add(b)
        self._invalidate_cache()

    def remove(self, a: T, b: T) -> None:
        """Remove dependency. A no longer depends on B"""

        if a in self.nodes and b in self.nodes[a]:
            self.nodes[a].remove(b)
            self._invalidate_cache()


class NamedAttr(Protocol):
    attr_name: str


class NamedAttrDependencyGraph[T: NamedAttr](DependencyGraph[T]):
    def ascend(self, path: Iterable[str]) -> T:
        """Traverse dependencies from root node"""

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
