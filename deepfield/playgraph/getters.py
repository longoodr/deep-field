import json
import logging
import os
from abc import ABC, abstractmethod
from hashlib import md5
from typing import Any, Dict, Iterable, List, Optional, Tuple

import networkx as nx
from peewee import chunked

from deepfield.dbmodels import (Game, Play, PlayEdge, PlayNode, clean_graph,
                                db, get_db_name)
from deepfield.enums import Outcome
from deepfield.playgraph.graph import Node, EdgeList

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class PlayGraphPersistenceChecker:
    """Will try returning an on-disk graph if the database's checksum matches
    the checksum for the on-disk graph at its time of creation; otherwise, will
    build the graph from scratch.
    """

    def __init__(self):
        db_name = os.path.splitext(get_db_name())[0]
        self._hash_filename = f"{db_name}_playgraph_hash.txt"

    def get_graph(self) -> nx.DiGraph:
        od_graph = self._get_on_disk_graph()
        if od_graph is not None:
            return od_graph
        graph = PlayGraphDbIterator().get_graph()
        PlayGraphDbWriter(graph).save_graph()
        self._write_hash()
        return graph

    def remove_files(self) -> None:
        clean_graph()
        try:
            os.remove(self._hash_filename)
        except FileNotFoundError:
            pass

    def is_on_disk_consistent(self) -> bool:
        """Returns whether the saved graph is consistent with the database."""
        return self._matches_db_hash()

    def _get_on_disk_graph(self) -> Optional[nx.DiGraph]:
        """If the on-disk graph is consistent with the database, return it;
        otherwise return None.
        """
        if not self.is_on_disk_consistent():
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

class _PlayGraphDbReader:
    """Reads the graph stored in the database."""

    def get_graph(self) -> nx.DiGraph:
        graph = nx.DiGraph()
        graph.add_nodes_from(self._get_nodes())
        graph.add_edges_from(self._get_edges())
        return graph

    @staticmethod
    def _get_nodes() -> Iterable[Tuple[int, Dict[str, Any]]]:
        query = PlayNode.select()
        interval_logger = _IntervalLogger(query.count(), "{} of {} nodes read")
        for i, n in enumerate(PlayNode.select()):
            yield (
                    n.play_id_id,
                    {"outcome": n.outcome}
                )
            interval_logger.log(i)

    @staticmethod
    def _get_edges() -> Iterable[Tuple[int, int]]:
        query = PlayEdge.select()
        interval_logger = _IntervalLogger(query.count(), "{} of {} edges read")
        for i, e in enumerate(query):
            yield (e.from_id_id, e.to_id_id)
            interval_logger.log(i)

class PlayGraphDbWriter:
    """Writes a graph to the database."""

    __NODES_PER_BATCH = 400
    __EDGES_PER_BATCH = 400

    def save_graph(self) -> None:
        clean_graph()
        with db.atomic():
            self._write_nodes()
            self._write_edges()
    
    def _write_nodes(self) -> None:
        for batch in chunked(self._get_node_data(), self.__NODES_PER_BATCH):
            PlayNode.insert_many(batch).execute()

    def _get_node_data(self) -> Iterable[Dict[str, Any]]:
        interval_logger = _IntervalLogger(len(self._graph), "{} of {} nodes written")
        for i, (play_id, data) in enumerate(self._graph.nodes(data=True)):
            yield {
                    "play_id": play_id,
                    "outcome": data["outcome"]
                }
            interval_logger.log(i)

    def _write_edges(self) -> None:
        for batch in chunked(self._get_edge_data(), self.__EDGES_PER_BATCH):
            PlayEdge.insert_many(batch).execute()

    def _get_edge_data(self) -> Iterable[Dict[str, Any]]:
        interval_logger = _IntervalLogger(self._graph.number_of_edges(), "{} of {} edges written")
        for i, (from_id, to_id) in enumerate(self._graph.edges):
            yield {
                "from_id": from_id,
                "to_id"  : to_id
            }
            interval_logger.log(i)

class PlayGraphDbIterator:
    """Reads plays from the database and produces the corresponding node and
    edge data.
    """

    def __init__(self):
        self._graph: nx.DiGraph = None

    def __iter__(self):
        self._plays = self.__get_plays()
        self._p2lp = Dict[int, int] = {} # short for "player to last play"
        return self

    def __next__(self) -> Tuple[Node, EdgeList]:
        node, play = self._get_next_node_and_play()
        edges = self._get_edges_from_play(play)
        return (node, edges)
        
    def _get_next_node_and_play(self) -> Tuple[Node, Any]:
        node = None
        while node is None:
            play = next(self._plays)
            node = self._get_node_from_play(play)
        return node, play

    def _get_edges_from_play(self, play) -> EdgeList:
        edges: EdgeList = []
        for player_id in [play.batter_id_id, play.pitcher_id_id]:
            if player_id in self._p2lp:
                edges.append((self._p2lp[player_id], play.id))
            self._p2lp[player_id] = play.id
        return edges

    @staticmethod
    def _get_node_from_play(play) -> Optional[Tuple[int, Dict[str, int]]]:
        outcome = Outcome.from_desc(play.desc)
        if outcome is None:
            return None
        return (play.id, {"outcome": outcome.value})

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

class _IntervalLogger:

    def __init__(self, total: int, fmt: str, intervals: int = 100):
        self._total = total
        self._fmt = fmt
        self._interval = max(1, total // intervals)

    def log(self, i: int):
        num = i + 1
        if num % self._interval == 0 or num == self._total:
                logger.info(self._fmt.format(num, self._total))
