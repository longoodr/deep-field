from typing import Iterable, Set

import networkx as nx


class GraphLayerer:
    """Returns layers of independent nodes in a DAG via BFS."""

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

    def get_layers(self) -> Iterable[Iterable]:
        """Iterates over the layers in the graph."""
        visited = set()
        nodes = self._source_nodes
        while len(nodes) > 0:
            yield nodes
            visited.update(nodes)
            succs = set()
            for n in nodes:
                succs.update([s for s in self._graph.successors(n)
                        if s not in visited]
                    )
            nodes = succs
