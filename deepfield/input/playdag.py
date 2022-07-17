from collections import Counter
from typing import Counter as CounterType, Dict, List, Tuple
import networkx as nx
from deepfield.input.reading import Matchup

from reading import DbMatchupReader

class PlayDagGenerator:
    """Iterates over input plays and maintains a dependency DAG
    of plays, which can be queried to construct input data.
    """
    
    bplays: Dict[int, List[Matchup]]
    pplays: Dict[int, List[Matchup]]
    dag: nx.DiGraph
    
    def __init__(self, reader: DbMatchupReader):
        self._reader = reader
        
    def __iter__(self):
        self._most_recent = None
        
        self.dag = nx.DiGraph()
        self.bplays: Dict[int, List[Matchup]] = {}
        self.pplays: Dict[int, List[Matchup]] = {}
        return iter(self._reader)
    
    def __next__(self) -> Matchup:
        """Incrementally builds the DAG from iterated plays.
        The properties of this object are updated in light of
        the new play. Returns the play that was updated on this
        iteration.
        """
        matchup = next(self._reader)
        (bid, pid, _, _) = matchup
        node = self._dag.add_node(matchup)
        
        bmatchup, pmatchup = self._get_last_plays(bid, pid)
        if bmatchup is not None:
            self._dag.add_edge(bmatchup, node)
        if pmatchup is not None:
            self._dag.add_edge(pmatchup, node)
        self._update_plays(matchup, bid, pid)
        return matchup
        
    def _update_plays(self, matchup: Matchup, bid: int, pid: int) -> None:
        for id_, plays in [(bid, self.bplays), (pid, self.pplays)]:
            if id_ in plays:
                plays[id_].append(matchup)
            else:
                plays[id_] = [matchup]
        
    def _get_last_plays(self, bid: int, pid: int) -> Tuple[Matchup, Matchup]:
        """Returns a tuple of the last matchups for the given players. The
        tuple entry will be None if the player hasn't been in a matchup yet.
        """
        bmatchup = None
        pmatchup = None
        if bid in self.bplays:
            bmatchup = self.bplays[-1]
        if pid in self.pplays:
            pmatchup = self.pplays[-1]
        return (bmatchup, pmatchup)