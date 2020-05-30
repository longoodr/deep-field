from abc import ABC, abstractmethod
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
        self._empty_rating = PlayerRating(num_stats)
        self.reset()

    def get_pitcher_rating(self, pid: int) -> np.ndarray:
        return self._get_player_rating(self._pratings, pid)

    def get_batter_rating(self, bid: int) -> np.ndarray:
        return self._get_player_rating(self._bratings, bid)

    def _get_player_rating(self,
                           ratings: Dict[int, "PlayerRating"],
                           id_: int
                           ) -> np.ndarray:
        if id_ not in ratings:
            return self._empty_rating.get_agg_rating()
        return ratings[id_].get_agg_rating()

    def reset(self):
        """Zeroes all player ratings."""
        self._bratings: Dict[int, "PlayerRating"] = {}
        self._pratings: Dict[int, "PlayerRating"] = {}
        self._avg_batter = PlayerRating(self._num_stats)
        self._avg_pitcher = PlayerRating(self._num_stats)

    def update(self, delta: np.ndarray, bid: int, pid: int)\
            -> None:
        """Updates the ratings for the given players."""
        self._update(delta, self._bratings, bid)
        self._update(delta, self._pratings, pid)
        self._avg_batter.update(delta)
        self._avg_pitcher.update(delta)

    def _update(self, delta, ratings: np.ndarray, id_: int) -> None:
        if id_ not in ratings:
            ratings[id_] = PlayerRating(self._num_stats)
        ratings[id_].update(delta)

    def get_node_pairwise_diffs(self, nodes: Iterable[Dict[str, int]]) -> np.ndarray:
        """Returns the pairwise differences for the given nodes."""
        diffs = [self.get_pairwise_diffs(n["batter_id"], n["pitcher_id"])
                 for n in nodes]
        return np.stack(diffs)

    def get_pairwise_diffs(self, bid: int, pid: int) -> np.ndarray:
        """Returns the pairwise difference matrix for the given players."""
        brating = self.get_batter_rating(bid)
        prating = self.get_pitcher_rating(pid)
        avg_pr = self._avg_pitcher.get_agg_rating()
        avg_br = self._avg_batter.get_agg_rating()
        return np.concatenate([brating - avg_br, prating - avg_pr], axis=None)

class PlayerRating:
    """A set of rating data for a given player."""

    SHORT_TERM_LENGTH = 100
    LONG_TERM_LENGTH = 1000
    CAREER_TERM_LENGTH = 10000

    SHORT_TERM_WEIGHT = 1 / SHORT_TERM_LENGTH
    LONG_TERM_WEIGHT = 1 / LONG_TERM_LENGTH
    CAREER_TERM_WEIGHT = 1 / CAREER_TERM_LENGTH

    def __init__(self, num_stats: int):
        self._num_stats = num_stats
        self.reset()

    def reset(self) -> None:
        """Resets this player's ratings and appearances to zero."""
        self._short_term = np.zeros(self._num_stats)
        self._long_term = np.zeros(self._num_stats)
        self._career = np.zeros(self._num_stats)

    def update(self, delta: np.ndarray) -> None:
        """Updates the player's ratings with the given delta."""
        self._short_term = self.SHORT_TERM_WEIGHT * delta \
                + (1 - self.SHORT_TERM_WEIGHT) * self._short_term
        self._long_term = self.LONG_TERM_WEIGHT * delta \
                + (1 - self.LONG_TERM_WEIGHT) * self._long_term
        self._career = self.CAREER_TERM_WEIGHT * delta \
                + (1 - self.CAREER_TERM_WEIGHT) * self._career

    def get_agg_rating(self) -> np.ndarray:
        ratings = [self._short_term, self._long_term, self._career]
        return np.concatenate(ratings, axis=None)