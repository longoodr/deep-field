import logging
from typing import Optional, Tuple

import h5py
import numpy as np
from keras.utils import Sequence

from deepfield.db.models import Game, Play
from deepfield.db.enums import Outcome

Matchup = Tuple[int, int, int, str]

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DbMatchupReader:
    """Reads plays from the database and produces the corresponding matchups
    in timestep-sequential order that need to be evaluated to generate input data.
    """

    LOG_FRAC_INTERVAL = 0.01

    def __iter__(self):
        query = self.__get_plays()
        self._plays = query.iterator()
        self._ct = query.count()
        self._num = 0
        self._num_none = 0
        self._next_frac = self.LOG_FRAC_INTERVAL
        return self

    def __next__(self) -> Matchup:
        node = None
        while node is None:
            play = next(self._plays)
            node = self._get_matchup_from_play(play)
        self._num += 1
        self._log_progress()
        return node

    def _log_progress(self):
        if self._num % 1000 != 0:
            return
        frac_none = self._num_none / self._num
        frac_not_none = 1 - frac_none
        est_ct = int(self._ct * frac_not_none)
        frac_processed = self._num / est_ct
        if frac_processed >= self._next_frac:
            logger.info(f"{self._num} of estimated total {est_ct} matchups read")
            self._next_frac += self.LOG_FRAC_INTERVAL

    def _get_matchup_from_play(self, play) -> Optional[Matchup]:
        outcome = Outcome.from_desc(play.desc)
        if outcome is None:
            self._num_none += 1
            return None
        return (play.batter_id, play.pitcher_id, outcome.value, play.game_id)

    @staticmethod
    def __get_plays():
        return (Play
                .select(Play.batter_id, Play.pitcher_id, Play.desc, Play.game_id)
                .join(Game, on=(Play.game_id == Game.id))
                .order_by(Game.date, Play.game_id, Play.play_num)
                .namedtuples()
            )

class ReadableDatafile(h5py.File):

    def __init__(self, name: str, *args, **kwargs):
        super().__init__(f"{name}.hdf5", "r", *args, **kwargs)
        self.x = self["x"]
        self.y = self["y"]

    def get_train_test_ids(self, batch_size: int, split: float = 0.05)\
            -> Tuple[np.ndarray, np.ndarray]:
        """Returns a random set of train and test batch IDs for this data."""
        indices = np.arange(int(len(self.x) / batch_size))
        np.random.shuffle(indices)
        train_test_partition = int((1 - split) * len(indices))
        train = indices[:train_test_partition]
        test = indices[train_test_partition:]
        return train, test

class DataGenerator(Sequence):
    """Reads x, y data for keras model training."""

    def __init__(self, db_name: str, ids: np.ndarray, batch_size: int, shuffle: bool = True):
        self._ids = ids
        self._shuffle = shuffle
        self._batch_size = batch_size
        df = ReadableDatafile(f"{db_name}.hdf5")
        self.x = df.x
        self.y = df.y
        self.on_epoch_end()

    def __len__(self):
        return len(self._ids)

    def __getitem__(self, i):
        index = self._ids[i]
        lo = index * self._batch_size
        hi = (index + 1) * self._batch_size
        x = self.x[lo:hi]
        y = self.y[lo:hi]
        return x, y

    def on_epoch_end(self):
        if self._shuffle:
            np.random.shuffle(self._ids)
