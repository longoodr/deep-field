from typing import Dict, List, Optional, Tuple
import networkx as nx
from deepfield.input.reading import Matchup, DbMatchupReader

class PlayDagGenerator:
    """Iterates over input plays and maintains a dependency DAG
    of plays, which can be queried to construct input data.
    """
    
    bplays: Dict[int, List[int]]
    pplays: Dict[int, List[int]]
    dag: nx.DiGraph
    
    def __init__(self):
        self._reader = DbMatchupReader()
        
    def __iter__(self):
        self._matchups = iter(self._reader)
        
        self.dag = nx.DiGraph()
        self.bplays = {}
        self.pplays = {}
        self._num = 0
        return self
    
    def __next__(self) -> Matchup:
        """Incrementally builds the DAG from iterated plays.
        The properties of this object are updated in light of
        the new play. Returns the play that was updated on this
        iteration.
        """
        matchup = next(self._matchups)
        (bid, pid, _, _) = matchup
        self.dag.add_node(self._num, matchup=matchup)
        
        bplay, pplay = self._get_last_plays(bid, pid)
        if bplay is not None:
            self.dag.add_edge(bplay, self._num)
        if pplay is not None:
            self.dag.add_edge(pplay, self._num)
        self._update_plays(self._num, bid, pid)
        
        self._num += 1
        return matchup
        
    def _update_plays(self, num: int, bid: int, pid: int) -> None:
        for id_, plays in [(bid, self.bplays), (pid, self.pplays)]:
            if id_ in plays:
                plays[id_].append(num)
            else:
                plays[id_] = [num]
        
    def _get_last_plays(self, bid: int, pid: int) -> Tuple[Optional[int], Optional[int]]:
        """Returns a tuple of the last matchups for the given players. The
        tuple entry will be None if the player hasn't been in a matchup yet.
        """
        bplay = None
        pplay = None
        if bid in self.bplays:
            bplay = self.bplays[bid][-1]
        if pid in self.pplays:
            pplay = self.pplays[pid][-1]
        return (bplay, pplay)