from abc import ABC, abstractmethod
from typing import Dict, Iterable, List, Tuple

import numpy as np

from deepfield.model.ratings import (KerasPredictionModel, PlayerRatings,
                                     PredictionModel)
from deepfield.model.transition import Candidate
from deepfield.playgraph.graph import LevelTraversal

class Population:
    """A set of candidates."""

    def __init__(self, pop_size: int, num_stats: int, layer_lengths: List[int]):
        self._pop = [
                Candidate.get_initial(num_stats, layer_lengths)
                for _ in range(pop_size)
            ]

    def zero_ratings(self) -> None:
        for cand in self._pop:
            cand.fitness = 0

    def resample(self) -> None:
        """Resamples the population according to member fitness."""
        # TODO
        pass

    def __iter__(self):
        self._cur = 0
        return self

    def __next__(self):
        return self._pop[self._cur]

class Trainer(ABC):
    """Implements model training loop."""

    def __init__(self, 
                 pop_size: int,
                 num_stats: int,
                 layer_lengths: List[int],
                 resample_after: int):
        self._pop_size = pop_size
        self._num_stats = num_stats
        self._layer_lengths = layer_lengths
        self._resample_after = resample_after

    def train(self):
        self._pop = Population(
                self._pop_size, self._num_stats, self._layer_lengths)
        num_seen = 0
        while not self._is_converged():
            self._pop.zero_ratings()
            for level in LevelTraversal():
                level = list(level)
                outcomes = np.asarray([n["outcome"] for n in level])
                for cand in self._pop:
                    self._train_and_update_cand(cand, level, outcomes)
                num_seen += len(level)
                if num_seen >= self._resample_after:
                    self._pop.resample()
                    num_seen = 0

    @staticmethod
    def _train_and_update_cand(cand: Candidate,
                               level: Iterable[Dict[str, int]],
                               outcomes: np.ndarray)\
                               -> None:
        diffs = cand.ratings.get_node_pairwise_diffs(level)
        kl_divs = cand.pred_model.backprop(diffs, outcomes)
        tot_kl_div = np.sum(kl_divs)
        cand.fitness -= tot_kl_div  # less divergence is better
        for i, node in enumerate(level):
            delta = cand.trans_geno[node["outcome"]] * kl_divs[i]
            cand.ratings.update(delta, node["batter_id"], node["pitcher_id"])

    def _is_converged(self):
        # TODO
        pass
