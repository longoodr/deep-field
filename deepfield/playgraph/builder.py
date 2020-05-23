from typing import Dict

import networkx as nx

from deepfield.enums import Outcome
from deepfield.scraping.dbmodels import Game, Play, init_db


class PlayGraphBuilder():
    """Builds a graph from plays in the database."""

    def __init__(self):
        self._graph: nx.DiGraph = None

    def get_graph(self) -> nx.DiGraph:
        if self._graph is not None:
            return self._graph
        player_to_last_play: Dict[int, int] = {}
        p2lp = player_to_last_play
        self._graph = nx.DiGraph()
        for play in self.__get_plays():
            self.__add_play(play, p2lp)
        return self._graph

    def __add_play(self, play, p2lp: Dict[int, int]) -> None:
        self._graph.add_node(
                play.id, 
                bid     = play.batter_id,
                pid     = play.pitcher_id,
                outcome = Outcome.from_desc(play.desc)
            )
        for player_id in [play.batter_id, play.pitcher_id]:
            if player_id in p2lp:
                self._graph.add_edge(p2lp[player_id], play.id)
            p2lp[player_id] = play.id

    @staticmethod
    def __get_plays():
        return (Play
                .select(Play.id, Play.batter_id, Play.pitcher_id, Play.desc)
                .join(Game, on=(Play.game_id == Game.id))
                .order_by(Game.date, Play.game_id, Play.play_num)
            )
