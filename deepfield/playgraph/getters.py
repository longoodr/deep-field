import json
import os
from abc import ABC, abstractmethod
from hashlib import md5
from typing import Dict, Optional

import networkx as nx
import networkx.readwrite.json_graph as json_graph

from deepfield.enums import Outcome
from deepfield.scraping.dbmodels import Game, Play, get_db_name


class _GraphGetter(ABC):
    """An object which can return a play dependency graph."""

    @abstractmethod
    def get_graph(self) -> nx.DiGraph:
        """Returns a play dependency graph."""
        pass

class PlayGraphPersistor(_GraphGetter):
    """Will try returning an on-disk graph if the database's checksum matches
    the checksum for the on-disk graph at its time of creation; otherwise, will
    build the graph from scratch.
    """

    def __init__(self):
        db_name = os.path.splitext(get_db_name())[0]
        self._graph_filename = f"{db_name}_playgraph.json"
        self._hash_filename = f"{db_name}_playgraph_hash.txt"

    def get_graph(self) -> nx.DiGraph:
        od_graph = self._get_on_disk_graph()
        if od_graph is not None:
            return od_graph
        graph = _PlayGraphBuilder().get_graph()
        self._save_graph(graph)
        return graph

    def remove_files(self) -> None:
        for filename in [self._graph_filename, self._hash_filename]:
            try:
                os.remove(filename)
            except FileNotFoundError:
                pass

    def _get_on_disk_graph(self) -> Optional[nx.DiGraph]:
        """If the on-disk graph is consistent with the database, return it;
        otherwise return None.
        """
        if not self._matches_db_hash():
            return None
        json = self._get_graph_json()
        if json is None:
            return None
        try:
            return json_graph.node_link_graph(json)
        except Exception:
            return None

    def _matches_db_hash(self) -> bool:
        hash_ = self._get_graph_hash()
        if hash_ is None:
            return False
        return self._get_db_hash() == hash_

    def _get_graph_json(self):
        try:
            with open(self._graph_filename, "r") as graph_file:
                return json.load(graph_file)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _get_graph_hash(self) -> Optional[str]:
        try:
            with open(self._hash_filename, "r") as hash_file:
                return hash_file.read()
        except FileNotFoundError:
            return None

    def _save_graph(self, graph: nx.DiGraph) -> None:
        with open(self._graph_filename, "w") as graph_file:
            json.dump(json_graph.node_link_data(graph), graph_file, indent=1)
        with open(self._hash_filename, "w") as hash_file:
            # file must exist at this point (would have exited if not)
            hash_file.write(self._get_db_hash())    # type: ignore

    def _get_db_hash(self) -> Optional[str]:
        return _ChecksumGenerator(get_db_name()).get_checksum()

class _PlayGraphBuilder(_GraphGetter):
    """Builds a graph from plays in the database."""

    def __init__(self):
        self._graph: nx.DiGraph = None

    def get_graph(self) -> nx.DiGraph:
        if self._graph is not None:
            return self._graph
        player_to_last_play: Dict[int, int] = {}
        p2lp = player_to_last_play  # a shorter alias
        self._graph = nx.DiGraph()
        for play in self.__get_plays():
            self.__add_play(play, p2lp)
        return self._graph

    def __add_play(self, play, p2lp: Dict[int, int]) -> None:
        outcome = Outcome.from_desc(play.desc)
        if outcome is None:
            return
        self._graph.add_node(
                play.id, 
                bid     = play.batter_id.id,
                pid     = play.pitcher_id.id,
                outcome = outcome.value
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

class _ChecksumGenerator:

    _BUFFER_SIZE = 4*1024

    def __init__(self, filename):
        self._name = filename
        self._checksum = None

    def get_checksum(self) -> Optional[str]:
        if self._checksum is None:
            try:
                self.__init_checksum()
            except FileNotFoundError:
                return None
        return self._checksum

    def __init_checksum(self) -> None:
        md5sum = md5()
        with open(self._name, "rb") as fileobj:
            for chunk in iter(lambda: fileobj.read(self._BUFFER_SIZE), b""):
                md5sum.update(chunk)
        self._checksum = md5sum.hexdigest()
