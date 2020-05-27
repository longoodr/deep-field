from abc import ABC, abstractmethod
from typing import Dict, Iterable, List, Tuple

import numpy as np

from deepfield.model.ratings import PlayerRatings, PredictionModel
from deepfield.model.transition import TransitionGenotype
from deepfield.playgraph.graph import LevelTraversal


class Candidate:
    """A candidate set of models used by the Trainer."""

    def __init__(self, pm: PredictionModel, tg: TransitionGenotype, pr: PlayerRatings):
        self.pred_model = pm
        self.trans_geno = tg
        self.ratings = pr
        self.fitness = 0

class Trainer(ABC):
    """Implements model training loop."""

    def __init__(self, pop_size: int, num_stats: int, resample_after: int):
        self._pop_size = pop_size
        self._num_stats = num_stats
        self._resample_after = resample_after

    def train(self):
        self._population = self._generate_inital_population()
        seen = 0
        while not self._is_converged():
            self._zero_ratings()
            for level in LevelTraversal():
                level = list(level)
                outcomes = np.asarray([n["outcome"] for n in level])
                for cand in self._population:
                    self._train_and_update(cand, level, outcomes)
                seen += len(level)
                if seen >= self._resample_after:
                    self._resample_population()
                    seen = 0

    def _train_and_update(self,
                          cand: Candidate,
                          level: Iterable[Dict[str, int]],
                          outcomes: np.ndarray) -> None:
        diffs = cand.ratings.get_node_pairwise_diffs(level)
        kl_divs = cand.pred_model.backprop(diffs, outcomes)
        tot_kl_div = np.sum(kl_divs)
        cand.fitness -= tot_kl_div
        for i, node in enumerate(level):
            delta = cand.trans_geno[node["outcome"]] * kl_divs[i]
            cand.ratings.update(delta, node["batter_id"], node["pitcher_id"])

    def _generate_inital_population(self) -> List[Candidate]:
        return [Candidate(
                self._generate_initial_prediction_model(),
                self._generate_initial_transition_genotype(),
                PlayerRatings(self._num_stats)
            ) for _ in range(self._pop_size)]
    
    def _zero_ratings(self) -> None:
        for cand in self._population:
            cand.fitness = 0

    @abstractmethod
    def _resample_population(self) -> None:
        pass

    @abstractmethod
    def _generate_initial_prediction_model(self) -> PredictionModel:
        pass

    @abstractmethod
    def _generate_initial_transition_genotype(self) -> TransitionGenotype:
        pass

    @abstractmethod
    def _is_converged(self):
        pass
