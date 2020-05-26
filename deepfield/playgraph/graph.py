from typing import Dict, Iterable, List, Set, Tuple

import networkx as nx

Node = Tuple[int, int, int]

class MaximalAntichainLattice:
    """Traverses the lattice of maximal antichains for a DAG."""

    def __init__(self, graph: nx.DiGraph):
        if not nx.is_directed_acyclic_graph(graph):
            raise ValueError("Must be DAG")
        self._graph = graph
        self._source_nodes = set([
                node 
                for node, indegree
                in self._graph.in_degree(self._graph.nodes())
                if indegree == 0
            ])

    def __iter__(self):
        self._visited = set()
        self._nodes = self._source_nodes
        return self

    def __next__(self) -> Iterable:
        if len(self._nodes) > 0:
            returned_nodes = self._nodes
            self._visited.update(self._nodes)
            succs = set()
            for n in self._nodes:
                succs.update([s for s in self._graph.successors(n)
                        if s not in self._visited
                        and self._visited.issuperset(self._graph.predecessors(s))]
                    )
            self._nodes = succs
            return returned_nodes
        else:
            raise StopIteration
