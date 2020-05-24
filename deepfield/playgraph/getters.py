import json
import logging
import os
from abc import ABC, abstractmethod
from hashlib import md5
from typing import Any, Dict, Iterable, Optional, Tuple

import networkx as nx
from peewee import chunked

from deepfield.dbmodels import (Game, Play, PlayEdge, PlayNode, clean_graph,
                                db, get_db_name)
from deepfield.enums import Outcome

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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

    __ROWS_PER_BATCH = 400

    def __init__(self):
        db_name = os.path.splitext(get_db_name())[0]
        self._hash_filename = f"{db_name}_playgraph_hash.txt"

    def get_graph(self) -> nx.DiGraph:
        od_graph = self._get_on_disk_graph()
        if od_graph is not None:
            return od_graph
        graph = _PlayGraphBuilder().get_graph()
        _PlayGraphDbWriter(graph).save_graph()
        self._write_hash()
        return graph

    def remove_files(self) -> None:
        clean_graph()
        try:
            os.remove(self._hash_filename)
        except FileNotFoundError:
            pass

    def _get_on_disk_graph(self) -> Optional[nx.DiGraph]:
        """If the on-disk graph is consistent with the database, return it;
        otherwise return None.
        """
        if not self._matches_db_hash():
            return None
        return _PlayGraphDbReader().get_graph()

    def _matches_db_hash(self) -> bool:
        hash_ = self._get_graph_hash()
        if hash_ is None:
            return False
        return self._get_db_hash() == hash_

    def _get_graph_hash(self) -> Optional[str]:
        try:
            with open(self._hash_filename, "r") as hash_file:
                return hash_file.read()
        except FileNotFoundError:
            return None

    def _write_hash(self) -> None:
        with open(self._hash_filename, "w") as hash_file:
            # file must exist at this point (would have exited if not)
            hash_file.write(self._get_db_hash())    # type: ignore

    def _get_db_hash(self) -> Optional[str]:
        return _ChecksumGenerator(get_db_name()).get_checksum()

class _PlayGraphDbReader(_GraphGetter):
    """Reads the graph stored in the database."""

    def get_graph(self) -> nx.DiGraph:
        graph = nx.DiGraph()
        graph.add_nodes_from(self._get_nodes())
        graph.add_edges_from(self._get_edges())
        return graph

    @staticmethod
    def _get_nodes() -> Iterable[Tuple[int, Dict[str, Any]]]:
        for n in PlayNode.select():
            yield (
                    n.play_id_id,
                    {"outcome": n.outcome}
                )

    @staticmethod
    def _get_edges() -> Iterable[Tuple[int, int]]:
        for e in PlayEdge.select():
            yield (e.from_id_id, e.to_id_id)

class _PlayGraphDbWriter:
    """Writes a graph to the database."""

    __NODES_PER_BATCH = 400
    __EDGES_PER_BATCH = 400

    def __init__(self, graph: nx.DiGraph):
        self._graph = graph

    def save_graph(self) -> None:
        clean_graph()
        with db.atomic():
            self._write_nodes()
            self._write_edges()
    
    def _write_nodes(self) -> None:
        for batch in chunked(self._get_node_data(), self.__NODES_PER_BATCH):
            PlayNode.insert_many(batch).execute()

    def _get_node_data(self) -> Iterable[Dict[str, Any]]:
        for play_id, data in self._graph.nodes(data=True):
            yield {
                    "play_id": play_id,
                    "outcome": data["outcome"]
                }

    def _write_edges(self) -> None:
        for batch in chunked(self._get_edge_data(), self.__EDGES_PER_BATCH):
            PlayEdge.insert_many(batch).execute()

    def _get_edge_data(self) -> Iterable[Dict[str, Any]]:
        for from_id, to_id in self._graph.edges:
            yield {
                "from_id": from_id,
                "to_id"  : to_id
            }

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
        plays = self.__get_plays()
        play_ct = plays.count()
        for i, play in enumerate(plays):
            self.__add_play(play, p2lp)
            if (i + 1) % 1000 == 0 or i + 1 == play_ct:
                logger.info(f"{i + 1} of {play_ct} plays processed")
        return self._graph

    def __add_play(self, play, p2lp: Dict[int, int]) -> None:
        outcome = Outcome.from_desc(play.desc)
        if outcome is None:
            return
        self._graph.add_node(
                play.id,
                outcome = outcome.value
            )
        for player_id in [play.batter_id_id, play.pitcher_id_id]:
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
