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
        self.reset()

    def get_pitcher_rating(self, pid: int) -> np.ndarray:
        if pid not in self._pratings:
            return np.zeros(self._num_stats)
        return self._pratings[pid][0]

    def get_batter_rating(self, bid: int) -> np.ndarray:
        if bid not in self._bratings:
            return np.zeros(self._num_stats)
        return self._bratings[bid][0]

    def reset(self):
        """Zeroes all player ratings."""
        self._bratings: Dict[int, List] = {}
        self._pratings: Dict[int, List] = {}

    def update(self, delta: np.ndarray, bid: int, pid: int)\
            -> None:
        """Updates the ratings for the given players."""
        if bid not in self._bratings:
            self._bratings[bid] = [np.zeros(self._num_stats), 0]
        if pid not in self._pratings:
            self._pratings[pid] = [np.zeros(self._num_stats), 0]
        brating, b_apps = self._bratings[bid]
        b_delta_weight = (1 / (b_apps + 1))
        new_brating = b_delta_weight * delta + (1 - b_delta_weight) * brating
        self._bratings[bid][0] = new_brating
        prating, p_apps = self._pratings[pid]
        p_delta_weight = (1 / (p_apps + 1))
        new_prating = p_delta_weight * delta + (1 - p_delta_weight) * prating
        self._pratings[pid][0] = -1 * new_prating
        self._bratings[bid][1] += 1
        self._pratings[pid][1] += 1

    def get_node_pairwise_diffs(self, nodes: Iterable[Dict[str, int]]) -> np.ndarray:
        """Returns the pairwise differences for the given nodes."""
        diffs = [self.get_pairwise_diffs(n["batter_id"], n["pitcher_id"])
                 for n in nodes]
        return np.stack(diffs)

    def get_pairwise_diffs(self, bid: int, pid: int) -> np.ndarray:
        """Returns the pairwise difference matrix for the given players."""
        brating = self.get_batter_rating(bid)
        prating = self.get_pitcher_rating(pid)
        b = np.tile(brating, (self._num_stats, 1))
        p = np.tile(prating, (self._num_stats, 1))
        return b - p.transpose()
