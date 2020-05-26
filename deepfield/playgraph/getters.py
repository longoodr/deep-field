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

class PlayGraphPersistor:
    """Maintains a consistent on-disk graph by check consistency and rewriting
    the graph if inconsistent.
    """

    def __init__(self):
        db_name = os.path.splitext(get_db_name())[0]
        self._hash_filename = f"{db_name}_playgraph_hash.txt"

    def ensure_consistency(self) -> bool:
        """If inconsistent, rewrites the graph; returns whether the graph was
        rewritten. After calling this, the graph is guaranteed to be
        consistent.
        """
        if self.is_on_disk_consistent():
            return False
        PlayGraphDbWriter().write_graph()
        self._write_graph_hash()
        return True

    def remove_files(self) -> None:
        clean_graph()
        try:
            os.remove(self._hash_filename)
        except FileNotFoundError:
            pass

    def is_on_disk_consistent(self) -> bool:
        """Returns whether the saved graph is consistent with the database."""
        return self._graph_and_db_hashes_match()

    def _graph_and_db_hashes_match(self) -> bool:
        graph_hash = self._get_graph_hash()
        if graph_hash is None:
            return False
        try:
            db_hash = self._get_db_hash()
        except FileNotFoundError:
            return False
        return db_hash == graph_hash

    def _get_graph_hash(self) -> Optional[str]:
        try:
            with open(self._hash_filename, "r") as hash_file:
                return hash_file.read()
        except FileNotFoundError:
            return None

    def _write_graph_hash(self) -> None:
        with open(self._hash_filename, "w") as hash_file:
            # file must exist at this point (would have exited if not)
            hash_file.write(self._get_db_hash())    # type: ignore

    def _get_db_hash(self) -> str:
        return _ChecksumGenerator(get_db_name()).get_checksum()

class GraphIterator(ABC):
    """An iterable which returns tuples of nodes along with edges from previous
    nodes to the returned node.
    """

    @abstractmethod
    def __iter__(self) -> "GraphIterator":
        pass

    @abstractmethod
    def __next__(self) -> Tuple[Node, EdgeList]:
        pass

class DbPlayGraphIterator(GraphIterator):
    """Reads the graph stored in the database."""

    def __iter__(self) -> GraphIterator:
        return self

    def __next__(self) -> Tuple[Node, EdgeList]:
        pass

class PlayGraphDbWriter:
    """Reads plays from the database and writes the corresponding play graph to
    the database.
    """

    __PER_BATCH = 200

    def write_graph(self) -> None:
        clean_graph()
        with db.atomic():
            self._write()
    
    def _write(self) -> None:
        for batch in chunked(DbPlaysToGraphIterator(), self.__PER_BATCH):
            nodes, edges = batch
            PlayNode.insert_many(nodes).execute()
            PlayEdge.insert_many(edges).execute()

class DbPlaysToGraphIterator(GraphIterator):
    """Reads plays from the database and produces the corresponding node and
    edge data for the associated play graph.
    """

    def __iter__(self) -> GraphIterator:
        self._plays = self.__get_plays()
        self._p2lp: Dict[int, int] = {} # short for "player to last play"
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

    def get_checksum(self) -> str:
        md5sum = md5()
        with open(self._name, "rb") as fileobj:
            for chunk in iter(lambda: fileobj.read(self._BUFFER_SIZE), b""):
                md5sum.update(chunk)
        return md5sum.hexdigest()

class _IntervalLogger:

    def __init__(self, total: int, fmt: str, intervals: int = 100):
        self._total = total
        self._fmt = fmt
        self._interval = max(1, total // intervals)

    def log(self, i: int):
        num = i + 1
        if num % self._interval == 0 or num == self._total:
                logger.info(self._fmt.format(num, self._total))
