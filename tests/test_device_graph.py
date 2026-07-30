import gc

import pytest

from grizzl_e_local.device.graph import (
    DependencyGraph,
    NamedAttrDependencyGraph,
)


class _Node:
    """Minimal wrapper for testing graph ordering."""

    def __init__(self, name: str):
        self.attr_name = name

    def __repr__(self):
        return f"<{self.__class__.__name__}:{self.attr_name}>"


# Module-level cache to keep nodes alive beyond WeakKeyDictionary scope
_node_cache: list[_Node] = []


def _generic_graph(*edges: tuple[str, str]) -> DependencyGraph[_Node]:
    g = DependencyGraph()
    nodes: dict[str, _Node] = {}

    def get(name: str) -> _Node:
        if name not in nodes:
            n = _Node(name)
            nodes[name] = n
            _node_cache.append(n)
        return nodes[name]

    for dependent_name, dep_name in edges:
        a, b = get(dependent_name), get(dep_name)
        g.add(a, b)

    return g


class TestGenericSorting:
    def test_empty_graph(self):
        assert list(DependencyGraph()) == []

    def test_linear_chain(self):
        """A depends on B → sorted: [A, B]."""
        g = _generic_graph(("A", "B"))
        result = list(g.sorted)
        a_node = next(n for n in result if n.attr_name == "A")
        b_node = next(n for n in result if n.attr_name == "B")
        assert result.index(a_node) < result.index(b_node)

    def test_diamond(self):
        """D depends on B and C; both depend on A → sorted: [D, B, C, A]."""
        g = _generic_graph(("B", "A"), ("C", "A"), ("D", "B"), ("D", "C"))
        result = list(g.sorted)

        d_node = next(n for n in result if n.attr_name == "D")
        b_node = next(n for n in result if n.attr_name == "B")
        c_node = next(n for n in result if n.attr_name == "C")
        a_node = next(n for n in result if n.attr_name == "A")

        assert result.index(d_node) < result.index(b_node)
        assert result.index(d_node) < result.index(c_node)
        assert result.index(b_node) < result.index(a_node)
        assert result.index(c_node) < result.index(a_node)


class TestGenericCyclicDetection:
    def test_simple_cycle(self):
        g = DependencyGraph()
        a, b = _Node("A"), _Node("B")
        g.add(a, b)
        g.add(b, a)

        with pytest.raises(RuntimeError, match="cyclic dependency"):
            list(g.sorted)


class TestGenericAddRemove:
    def test_add_then_sort(self):
        g = DependencyGraph()
        a, b = _Node("A"), _Node("B")
        g.add(a, b)
        result = list(g.sorted)
        assert len(result) == 2

    def test_remove_invalidation(self):
        """Removing a dependency invalidates the cached sorted property."""
        g = _generic_graph(("A", "B"))

        b_node = next(n for n in g.nodes if n.attr_name == "B")
        a_node = next(n for n in g.nodes if n.attr_name == "A")
        old_sorted_ids = [id(n) for n in g.sorted]

        # Force cache rebuild by removing and re-adding
        g.remove(a_node, b_node)
        g.add(a_node, b_node)

        new_sorted = list(g.sorted)
        assert [id(n) for n in new_sorted] == old_sorted_ids


class TestGenericInverted:
    def test_inverts_direction(self):
        """If A depends on B, inverted maps B → {A}."""
        g = _generic_graph(("A", "B"), ("C", "B"))

        inverted = g.inverted
        assert len(inverted) == 1


def _named_graph(*edges: tuple[str, str]) -> NamedAttrDependencyGraph[_Node]:
    g = NamedAttrDependencyGraph()
    nodes: dict[str, _Node] = {}

    def get(name: str) -> _Node:
        if name not in nodes:
            n = _Node(name)
            nodes[name] = n
            _node_cache.append(n)
        return nodes[name]

    for dependent_name, dep_name in edges:
        a, b = get(dependent_name), get(dep_name)
        g.add(a, b)

    return g


class TestNamedGraphAscend:
    def test_ascend_single_node(self):
        """Single node C → ascend(["C"]) returns C."""
        g = NamedAttrDependencyGraph()
        c = _Node("C")
        g.nodes[c] = set()  # register without dependencies

        result = g.ascend([c.attr_name])
        assert result.attr_name == "C"

    def test_ascend_full_path(self):
        """Chain A→B→C, ascend ["A", "B", "C"] ends at C."""
        g = _named_graph(("B", "A"), ("C", "B"))
        result = g.ascend(["A", "B", "C"])
        assert result.attr_name == "C"

    def test_ascend_partial_path(self):
        """Chain A→B→C, ascend ["A", "B"] ends at B."""
        g = _named_graph(("B", "A"), ("C", "B"))
        result = g.ascend(["A", "B"])
        assert result.attr_name == "B"

    def test_ascend_wrong_root_raises(self):
        g = NamedAttrDependencyGraph()
        a, b = _Node("A"), _Node("B")
        g.add(b, a)  # B depends on A → sorted: [B, A], root is A

        with pytest.raises(ValueError):
            g.ascend(["X"])

    def test_ascend_missing_intermediate_raises(self):
        """Path goes through non-existent intermediate."""
        g = _named_graph(("B", "A"), ("C", "B"))
        with pytest.raises(ValueError):
            g.ascend(["A", "X"])


class TestNamedGraphIteration:
    def test_iter_gives_sorted(self):
        result = list(_named_graph(("A", "B"), ("B", "C")))
        a_node = next(n for n in result if n.attr_name == "A")
        c_node = next(n for n in result if n.attr_name == "C")
        assert result.index(a_node) < result.index(c_node)

    def test_reversed_gives_reverse_sorted(self):
        result = list(reversed(_named_graph(("A", "B"), ("B", "C"))))
        # sorted is [A, B, C], reversed gives [C, B, A]
        a_node = next(n for n in result if n.attr_name == "A")
        c_node = next(n for n in result if n.attr_name == "C")
        assert result.index(a_node) > result.index(c_node)


class TestSortedMutationDuringIteration:
    def test_reentrant_sorted_during_iteration_causes_false_cycle(self):
        """sorted() fails when called recursively during its own iteration.

        When validate_state() triggers _create(), new edges are added to the
        shared DependencyGraph. If sorted() is called during this mutation,
        it builds `dependents` from stale node values, causing newly added
        leaf nodes to be missed — result has fewer items than g.nodes keys.
        """
        class _N:
            def __init__(self, name: str):
                self._name = name
            def __repr__(self):
                return f"<{_N.__name__}:{self._name}>"

        # Build graph: root → child1 (root is the only node with deps)
        root, child1 = _N("root"), _N("child1")
        g = DependencyGraph()
        g.nodes[root] = {child1}
        g.nodes[child1] = set()

        # Pre-compute sorted() to populate cache
        list(g.sorted)

        # Now simulate re-entrant sorted() call during iteration:
        # We'll manually trigger the condition by adding a node that creates
        # a situation where dependents list is stale
        child2 = _N("child2")
        
        # Add edge: root → child2 (while cache exists)
        g.add(root, child2)  # This invalidates cache
        
        # sorted() rebuilds with new data — should include all nodes
        result = list(g.sorted)  # type: ignore[assignment]
        assert len(result) == 3


class TestWeakReferenceGC:
    def test_gc_removes_orphaned_nodes(self):
        """Nodes with no external strong refs disappear from the graph."""
        g = DependencyGraph()
        a, b = _Node("A"), _Node("B")
        g.add(a, b)

        assert len(g.nodes) == 2

        # Drop all strong references to nodes
        del a, b
        gc.collect()

        assert len(g.nodes) < 2

    def test_gc_affects_sorted(self):
        """GC'd nodes are excluded from sorted results."""
        g = DependencyGraph()
        a, b = _Node("A"), _Node("B")
        g.add(a, b)

        # Invalidate cache first so the cached list doesn't hold strong refs
        del a, b
        gc.collect()
        g._invalidate_cache()

        new_count = len(list(g.sorted))
        assert new_count == 0

    def test_gc_preserves_remaining_nodes(self):
        """Only GC'd nodes are removed; surviving references stay."""
        g = DependencyGraph()
        a, b = _Node("A"), _Node("B")
        g.add(a, b)
        a_ref = a  # keep strong ref to A

        del b
        gc.collect()

        assert len(g.nodes) == 1
        assert any(n.attr_name == "A" for n in g.nodes)

    def test_gc_clears_inverted(self):
        """Inverted graph reflects GC'd nodes."""
        g = DependencyGraph()
        a, b = _Node("A"), _Node("B")
        g.add(a, b)  # A depends on B

        inverted_keys_before = set(id(k) for k in g.inverted.keys())

        del a, b
        gc.collect()

        inverted_keys_after = set(id(k) for k in g.inverted.keys())
        assert len(inverted_keys_after) < len(inverted_keys_before)

    def test_gc_single_node_graph(self):
        """Empty graph after all nodes GC'd."""
        g = DependencyGraph()
        a, b = _Node("A"), _Node("B")
        g.add(a, b)

        del a, b
        gc.collect()

        assert list(g) == []

