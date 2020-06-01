import os
from hashlib import md5
from typing import Iterator, Optional

import h5py
from tensorflow.keras.utils import to_categorical

from deepfield.dbmodels import (PlayNode, clean_graph, db, get_data_name,
                                get_db_name)
from deepfield.enums import Outcome
from deepfield.input.ratings import PlayerRatings
from deepfield.input.reading import DbMatchupReader


class InputDataPersistor:
    """Maintains a consistent on-disk input dataset by check consistency and
    rewriting the data if inconsistent.
    """

    def __init__(self):
        db_name = os.path.splitext(get_db_name())[0]
        self._hash_filename = f"{db_name}_data_hash.txt"

    def ensure_consistency(self) -> bool:
        """If inconsistent, rewrites the data; returns whether the data was
        rewritten.
        """
        if self.is_consistent():
            return False
        _InputDataWriter().write_data()
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

class _InputDataWriter:
    """Reads plays from the database and writes the corresponding input data."""

    _PER_BATCH = 300

    def write_data(self) -> None:
        ratings = PlayerRatings()
        rating_shape = ratings.get_matchup_rating(0, 0).shape
        with h5py.File("data", "w") as data_file:
            x = data_file.create_dataset("x", (1, *rating_shape), chunks=True,
                    maxshape=(None, *rating_shape))
            y = data_file.create_dataset("y", (1, len(Outcome)), chunks=True,
                    maxshape=(None, len(Outcome)))
            for i, (bid, pid, outcome) in enumerate(iter(DbMatchupReader())):
                self._write_matchup(i, bid, pid, outcome, ratings, x, y)

    def _write_matchup(self,
                       num: int,
                       bid: int,
                       pid: int,
                       outcome: int,
                       ratings: PlayerRatings,
                       x: h5py.Dataset,
                       y: h5py.Dataset
                       ) -> None:
        outcome_oh = to_categorical(outcome, len(Outcome))
        x.resize(num + 1, axis=0)
        y.resize(num + 1, axis=0)
        x[num] = ratings.get_matchup_rating(bid, pid)
        y[num] = outcome_oh
        ratings.update(bid, pid, outcome_oh)

    @classmethod
    def _write_next_batch(cls, nodes: Iterator) -> None:
        batch = []
        try:
            for _ in range(cls._PER_BATCH):
                batch.append(next(nodes))
        except StopIteration:
            PlayNode.insert_many(batch, fields = ("play_id", "outcome", "level")).execute()
            raise StopIteration
        PlayNode.insert_many(batch, fields = ("play_id", "outcome", "level")).execute()

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
