from abc import ABC, abstractmethod
from math import exp, log
from typing import Dict, Iterable, List, Set, Tuple

import numpy as np
from scipy.special import softmax
from tensorflow.keras import backend as K
from tensorflow.keras.layers import Activation, Dense, Flatten, InputLayer
from tensorflow.keras.losses import kullback_leibler_divergence as kl_div
from tensorflow.keras.models import Model, Sequential, clone_model
from tensorflow.keras.utils import to_categorical

from deepfield.enums import Outcome


class Batcher:
    """Because of the variable-length levels inherent in the structure of
    the play dependency graph, batch size is variable among training and
    prediction calls to the model, which triggers retracing of the 
    computation graph and slows down training. For this reason, batches
    need to be made uniform size.
    """

    PAD_SIZE = 2 ** 6

    @classmethod
    def pad_batch(cls, batch: np.ndarray) -> np.ndarray:
        """Rounds the given batch size up to the next power of 2 by padding the
        empty batch samples with zeroes. Returns the padded batch.
        """
        unpadded_size: int = batch.shape[0]
        if unpadded_size == cls.PAD_SIZE:
            return batch
        pad_length = cls.PAD_SIZE - unpadded_size
        sample_shape = batch.shape[1:]
        dup_samples = np.stack([np.zeros(sample_shape)for _ in range(pad_length)])
        padded_batch = np.concatenate([batch, dup_samples])
        return padded_batch

    @classmethod
    def get_padded_weights(cls, unpadded_size: int):
        """Returns the sample weight array to ignore the samples when the given
        batch is padded.
        """
        if unpadded_size == cls.PAD_SIZE:
            return np.ones(cls.PAD_SIZE)
        pad_length = cls.PAD_SIZE - unpadded_size
        return cls._get_padded_weights(unpadded_size, pad_length)

    @staticmethod
    def _get_padded_weights(unpadded_size: int, pad_length: int) -> np.ndarray:
        unpadded_weights = np.ones(unpadded_size)
        weight_padding = np.zeros(pad_length)
        return np.concatenate([unpadded_weights, weight_padding])

class PredictionModel:
    """A wrapper around a model which predicts outcome distributions from 
    player stat pairwise differences.
    """

    def __init__(self, model: Model):
        self.model = model

    def backprop(self,
                 pairwise_diffs: np.ndarray,
                 outcomes: np.ndarray, 
                 weights: np.ndarray
            ) -> np.ndarray:
        self.model.train_on_batch(pairwise_diffs, outcomes)
        return K.eval(kl_div(K.variable(outcomes), self.model(pairwise_diffs)))

    def predict(self, pairwise_diffs: np.ndarray) -> np.ndarray:
        return K.eval(self.model(pairwise_diffs))

class PlayerRatings:
    """A set of ratings for players that can be updated as plays are 
    evaluated.
    """

    def __init__(self, num_stats: int):
        self._num_stats = num_stats
        self.reset()

    def get_batter(self, bid: int) -> PlayerRating:
        if bid not in self._bratings:
            self._bratings[bid] = PlayerRating(self._avg_batter)
        return self._bratings[bid]

    def get_pitcher(self, pid: int) -> PlayerRating:
        if pid not in self._pratings:
            self._pratings[pid] = PlayerRating(self._avg_pitcher)
        return self._pratings[pid]

    def reset(self):
        """Resets all player ratings."""
        self._bratings: Dict[int, "PlayerRating"] = {}
        self._pratings: Dict[int, "PlayerRating"] = {}
        self._avg_batter = AvgPlayerRating()
        self._avg_pitcher = AvgPlayerRating()

    def update(self, event: np.ndarray, bid: int, pid: int)\
            -> None:
        """Updates the ratings for the given players."""
        self.get_batter(bid).update(event)
        self.get_pitcher(pid).update(event)
        self._avg_batter.update(event)
        self._avg_pitcher.update(event)

    def get_matchup_ratings(self, nodes: Iterable[Dict[str, int]]) -> np.ndarray:
        """Returns the matchup ratings for the given nodes."""
        diffs = [self.get_matchup_rating(n["batter_id"], n["pitcher_id"])
                 for n in nodes]
        return np.stack(diffs)

    def get_matchup_rating(self, bid: int, pid: int) -> np.ndarray:
        """Returns the matchup rating for the given players."""
        brating = self.get_batter(bid)
        prating = self.get_pitcher(pid)
        b_vs_avg = brating.get_rating() - self._avg_batter.get_rating()
        p_vs_avg = prating.get_rating() - self._avg_pitcher.get_rating()
        return np.concatenate(
                [
                    b_vs_avg,
                    p_vs_avg,
                    brating.appearances,
                    prating.appearances,
                ],
                axis=None
            )

class AbstractPlayerRating:
    """Tracks rating data for matchups."""

    def __init__(self, subratings: Iterable["AbstractSubrating"]):
        self._subratings = list(subratings)

    def reset(self) -> None:
        """Resets the rating to its initial value."""
        for subrating in self._subratings:
            subrating.reset()

    def update(self, event: np.ndarray) -> None:
        """Updates the ratings with the given event. This should be a one-hot
        vector.
        """
        for subrating in self._subratings:
            subrating.update(event)

    def get_rating(self) -> np.ndarray:
        """Returns the value of this rating."""
        return np.concatenate(self._subratings, axis=None)

class AvgPlayerRating(AbstractPlayerRating):
    """Represents the rating of the average player at a given point in time."""

    def __init__(self):
        self.short_term = AvgPlayerSubrating(1000)
        self.mid_term = AvgPlayerSubrating(10000)
        self.long_term = AvgPlayerSubrating(100000)
        subratings = [self.short_term, self.mid_term, self.long_term]
        super().__init__(subratings)

class PlayerRating(AbstractPlayerRating):
    """A set of rating data for a given player."""

    def __init__(self, avg_rating: AvgPlayerRating):
        self.short_term = PlayerSubrating(100, avg_rating.short_term)
        self.mid_term = PlayerSubrating(1000, avg_rating.mid_term)
        self.long_term = PlayerSubrating(10000, avg_rating.long_term)
        subratings = [self.short_term, self.mid_term, self.long_term]
        super().__init__(subratings)
        self.appearances = 0

    def update(self, event: np.ndarray) -> None:
        super().update(event)
        self.appearances += 1

class AbstractSubrating(ABC):
    """A moving average of performance over a given number of plays."""

    def __init__(self, plays_over: int):
        self.rating = self._initial_value()
        self._weight = 1 / plays_over

    def update(self, event: np.ndarray) -> None:
        update_funcs = [
                self._pos_update if event[i] >= self.rating[i]
                else self._neg_update
                for i in range(event.size)
            ]
        self.rating = np.asarray([
                update(x) for update, x in zip(update_funcs, self.rating)
            ])

    # see https://www.desmos.com/calculator/lffptb95tq for a visual explanation
    # of these updates
    def _pos_update(self, x):
        return 1 - exp(log(1-x) - self._weight)

    def _neg_update(self, x):
        return exp(log(x) - self._weight)

    def reset(self) -> None:
        """Resets this rating to its initial value."""
        self.rating = self._initial_value()

    @abstractmethod
    def _initial_value(self) -> np.ndarray:
        """Returns the initial value of this rating."""
        pass

class AvgPlayerSubrating(AbstractSubrating):
    """The average player's initial value is the percentage array for outcomes
    over all plays in the database.
    """

    _init_val = Outcome.get_percentages()

    def _initial_value(self) -> np.ndarray:
        return self._init_val

class PlayerSubrating(AbstractSubrating):
    """A player's initial value is whatever the current average player rating
    is.
    """

    def __init__(self, plays_over: int, avg_subrating: AvgPlayerSubrating):
        self._avg = avg_subrating
        super().__init__(plays_over)

    def _initial_value(self):
        return self._avg.rating