import os
from hashlib import md5
from typing import Iterator, Optional

import h5py
from tensorflow.keras.utils import to_categorical

from deepfield.dbmodels import db, get_data_name, get_db_name
from deepfield.enums import Outcome
from deepfield.input.ratings import PlayerRatings
from deepfield.input.reading import DbMatchupReader


class InputDataPersistor:
    """Maintains a consistent on-disk input dataset by check consistency and
    rewriting the data if inconsistent.
    """

    def __init__(self):
        db_name = os.path.splitext(get_db_name())[0]
        self._data_filename = f"{get_data_name()}.hdf5"
        self._hash_filename = f"{db_name}_data_hash.txt"

    def ensure_consistency(self) -> bool:
        """If inconsistent, rewrites the data; returns whether the data was
        rewritten.
        """
        if self.is_consistent():
            return False
        self._write_data()
        self._write_data_hash()
        return True

    def remove_files(self) -> None:
        for filename in [self._data_filename, self._hash_filename]:
            try:
                os.remove(filename)
            except FileNotFoundError:
                pass

    def is_consistent(self) -> bool:
        """Returns whether the saved data is consistent with the database."""
        return self._data_and_db_hashes_match()

    def _data_and_db_hashes_match(self) -> bool:
        data_hash = self._get_data_hash()
        if data_hash is None:
            return False
        try:
            db_hash = self._get_db_hash()
        except FileNotFoundError:
            return False
        return db_hash == data_hash

    def _get_data_hash(self) -> Optional[str]:
        try:
            with open(self._hash_filename, "r") as hash_file:
                return hash_file.read()
        except FileNotFoundError:
            return None

    def _write_data_hash(self) -> None:
        with open(self._hash_filename, "w") as hash_file:
            hash_file.write(self._get_db_hash())

    def _get_db_hash(self) -> str:
        return ChecksumGenerator(get_db_name()).get_checksum()

    def _write_data(self) -> None:
        with WritableDatafile(get_data_name()) as df:
            for i, (bid, pid, outcome) in enumerate(iter(DbMatchupReader())):
                df.write_matchup(i, bid, pid, outcome)

class ChecksumGenerator:

    _BUFFER_SIZE = 4*1024

    def __init__(self, filename):
        self._name = filename

    def get_checksum(self) -> str:
        md5sum = md5()
        with open(self._name, "rb") as fileobj:
            for chunk in iter(lambda: fileobj.read(self._BUFFER_SIZE), b""):
                md5sum.update(chunk)
        return md5sum.hexdigest()

class WritableDatafile(h5py.File):
    """Writes matchups to an hdf5 file."""

    def __init__(self, name: str, *args, **kwargs):
        super().__init__(name, "w", *args, **kwargs)
        self.__ratings = PlayerRatings()
        rating_shape = self.__ratings.get_matchup_rating(0, 0).shape
        self.__x = self.create_dataset("x", (1, *rating_shape), chunks=True,
                    maxshape=(None, *rating_shape))
        self.__y = self.create_dataset("y", (1, len(Outcome)), chunks=True,
                    maxshape=(None, len(Outcome)))

    def write_matchup(self, num: int, bid: int, pid: int, outcome: int) -> None:
        outcome_oh = to_categorical(outcome, len(Outcome))
        self.__x.resize(num + 1, axis=0)
        self.__y.resize(num + 1, axis=0)
        self.__x[num] = self.__ratings.get_matchup_rating(bid, pid)
        self.__y[num] = outcome_oh
        self.__ratings.update(bid, pid, outcome_oh)