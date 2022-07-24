from typing import Callable, Dict, List
import networkx as nx
from deepfield.input.reading import Matchup, DbMatchupReader

class PlayDagGenerator:
    """Iterates over input plays and maintains a dependency DAG
    of plays, which can be queried to construct input data.
    """

    player_to_plays: Dict[int, List[int]]
    dag: nx.DiGraph

    def __init__(self):
        self._reader = DbMatchupReader()

    def build_dag(self, callback) -> nx.DiGraph:
        """Builds the DAG from iterated plays.
        """
        for m in self:
            callback(m)
        return self.dag

    def __iter__(self):
        self._matchups = iter(self._reader)

        self.dag = nx.DiGraph()
        self.player_to_plays = {}
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
        self.dag.add_node(self._num, matchup=matchup,
            bheight=len(self._get_player_plays(bid)),
            pheight=len(self._get_player_plays(pid)),
            num=self._num)

        for player_id in [bid, pid]:
            last_play = self._get_last_play(player_id)
            if last_play is not None:
                self.dag.add_edge(last_play, self._num)

        self._update_plays(self._num, bid, pid)
        self._num += 1
        return matchup

    def _get_player_plays(self, player_id: int) -> List[int]:
        if player_id not in self.player_to_plays:
            return []
        return self.player_to_plays[player_id]

    def _update_plays(self, num: int, bid: int, pid: int) -> None:
        for player_id in [bid, pid]:
            if player_id in self.player_to_plays:
                self.player_to_plays[player_id].append(num)
            else:
                self.player_to_plays[player_id] = [num]

    def _get_last_play(self, player_id: int) -> int:
        plays = self._get_player_plays(player_id)
        if len(plays) == 0:
            return None
        return plays[-1]
