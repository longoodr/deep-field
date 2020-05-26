import json
import logging
import os
from abc import ABC, abstractmethod
from collections import Counter
from hashlib import md5
from typing import Any
from typing import Counter as CounterType
from typing import Dict, Iterable, List, Optional, Tuple

import networkx as nx
from peewee import chunked

from deepfield.dbmodels import (Game, Play, PlayNode, clean_graph, db,
                                get_db_name)
from deepfield.enums import Outcome
from deepfield.playgraph.graph import Node

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
        rewritten.
        """
        if self.is_consistent():
            return False
        _PlayGraphDbWriter().write_graph()
        self._write_graph_hash()
        return True

    def remove_files(self) -> None:
        clean_graph()
        try:
            os.remove(self._hash_filename)
        except FileNotFoundError:
            pass

    def is_consistent(self) -> bool:
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
            hash_file.write(self._get_db_hash())

    def _get_db_hash(self) -> str:
        return _ChecksumGenerator(get_db_name()).get_checksum()

class _PlayGraphDbWriter:
    """Reads plays from the database and writes the corresponding play graph to
    the database.
    """

    _PER_BATCH = 300

    def write_graph(self) -> None:
        clean_graph()
        with db.atomic():
            self._write_nodes()
    
    def _write_nodes(self) -> None:
        for batch in chunked(_DbPlaysToGraphIterator(), self._PER_BATCH):
            PlayNode.insert_many(batch, fields = ("play_id", "outcome", "level")).execute()

class _DbPlaysToGraphIterator():
    """Reads plays from the database and produces the corresponding nodes for
    the associated play graph.
    """

    def __iter__(self):
        query = self.__get_plays()
        self._plays = iter(query)
        self._ct = query.count()
        # maps player id to level of their last play + 1 (i.e. 0 => no plays)
        # (+ 1, because node levels should be 0-indexed)
        self._player_to_lvl: CounterType[int] = Counter()
        self._num = 0
        return self

    def __next__(self) -> Node:
        node = None
        while node is None:
            play = next(self._plays)
            node = self._get_node_from_play(play)
        self._num += 1
        if self._num % 1000 == 0:
            logger.info(f"{self._num} of roughly {self._ct} nodes processed")
        return node

    def _get_node_from_play(self, play) -> Optional[Node]:
        outcome = Outcome.from_desc(play.desc)
        if outcome is None:
            return None
        level = self._get_node_level(play)
        self._player_to_lvl[play.batter_id] = level + 1
        self._player_to_lvl[play.pitcher_id] = level + 1
        return (play.id, outcome.value, level)

    def _get_node_level(self, play) -> int:
        bid = play.batter_id
        pid = play.pitcher_id
        b_lvl = self._player_to_lvl[bid]
        p_lvl = self._player_to_lvl[pid]
        return max(b_lvl, p_lvl)

    @staticmethod
    def __get_plays():
        return (Play
                .select(Play.id, Play.batter_id, Play.pitcher_id, Play.desc)
                .join(Game, on=(Play.game_id == Game.id))
                .order_by(Game.date, Play.game_id, Play.play_num)
                .namedtuples()
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
