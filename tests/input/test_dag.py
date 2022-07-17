import networkx as nx

from tests import utils
from deepfield.input.playdag import PlayDagGenerator

class TestDag:
    
    @classmethod
    def setup_class(cls):
        utils.init_test_env()
        utils.insert_natls_game()
        
    def test_dag(self):
        gen = PlayDagGenerator()
        num = 0
        for m in gen:
            assert nx.is_directed_acyclic_graph(gen.dag)
            assert nx.get_node_attributes(gen.dag, "matchup")[num] == m
            immediate_prevs = list(gen.dag.neighbors(num))
            assert len(immediate_prevs) <= 2
            num += 1

        for i, tier in enumerate(nx.topological_generations(gen.dag)):
            seen_bids = set()
            seen_pids = set()
            for n in tier:
                node = gen.dag.nodes[n]
                (bid, pid, _, _) = node["matchup"]
                assert (i >= max(node["bheight"], node["pheight"]))
                assert bid not in seen_bids
                assert pid not in seen_pids
                seen_bids.add(bid)
                seen_pids.add(pid)
                
