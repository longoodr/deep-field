from abc import ABC, abstractmethod
from typing import Dict, Iterable

import numpy as np


class PredictionModel(ABC):
    """A model which predicts outcome distributions from player stat pairwise
    differences.
    """

    @abstractmethod
    def backprop(self, pairwise_diffs) -> None:
        pass

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
        return self._pratings[pid]

    def get_batter_rating(self, bid: int) -> np.ndarray:
        if bid not in self._bratings:
            return np.zeros(self._num_stats)
        return self._bratings[bid]

    def copy(self) -> "PlayerRatings":
        cp = PlayerRatings(self._num_stats)
        cp._bratings = self._copy_ratings(self._bratings)
        cp._pratings = self._copy_ratings(self._pratings)
        return cp
    
    @staticmethod
    def _copy_ratings(ratings: Dict[int, np.ndarray]) -> Dict[int, np.ndarray]:
        return {id_: r.copy() for id_, r in ratings.items()}

    def reset(self):
        """Zeroes all player ratings."""
        self._bratings: Dict[int, np.ndarray] = {}
        self._pratings: Dict[int, np.ndarray] = {}

    def update(self, delta: np.ndarray, bid: int, pid: int)\
            -> None:
        """Updates the ratings for the given players."""
        if bid not in self._bratings:
            self._bratings[bid] = np.zeros(self._num_stats)
        if pid not in self._pratings:
            self._pratings[pid] = np.zeros(self._num_stats)
        self._bratings[bid] += delta
        self._pratings[pid] -= delta

    def get_node_pairwise_diffs(self, nodes: Iterable[Dict[str, int]]) -> Iterable[np.ndarray]:
        """Returns the pairwise differences for the given nodes."""
        for node in nodes:
            yield self.get_pairwise_diffs(node["batter_id"], node["pitcher_id"])

    def get_pairwise_diffs(self, bid: int, pid: int) -> np.ndarray:
        """Returns the pairwise difference matrix for the given players."""
        brating = self.get_batter_rating(bid)
        prating = self.get_pitcher_rating(pid)
        b = np.tile(brating, (self._num_stats, 1))
        p = np.tile(prating, (self._num_stats, 1))
        return b - p.transpose()
