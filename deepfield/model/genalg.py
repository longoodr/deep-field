from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
from scipy.special import softmax

from deepfield.model.ratings import (KerasPredictionModel, PlayerRatings,
                                     PredictionModel)
from deepfield.model.transition import Candidate
from deepfield.playgraph.graph import LevelTraversal


class GenAlgParams:
    """A set of parameters for the genetic algorithm."""

    def __init__(self,
                 best_n_frac: float,
                 mutation_frac: float,
                 resample_after: int,
                 num_stats: int):
        for frac in [best_n_frac, mutation_frac]:
            if frac < 0 or frac > 1:
                raise ValueError
        self.best_n_frac = best_n_frac
        self.mutation_frac = mutation_frac
        self.resample_after = resample_after
        self.num_stats = num_stats

class Population:
    """A set of candidates."""

    def __init__(self,
                 pop_size: int,
                 layer_lengths: List[int],
                 ga_params: GenAlgParams):
        self._pop_size = pop_size
        self._layer_lengths = layer_lengths
        self._ga_params = ga_params
        self._pop = [
                Candidate.get_initial(self._ga_params.num_stats, layer_lengths)
                for _ in range(pop_size)
            ]

    def zero_ratings(self) -> None:
        for cand in self._pop:
            cand.fitness = 0

    def process_level(self, level: Iterable[Dict[str, int]]) -> None:
        """Backprops the level data for each candidate and updates ratings."""
        level = list(level)
        outcomes = np.asarray([n["outcome"] for n in level])
        for cand in self._pop:
            cand.train_and_update(level, outcomes)

    def resample(self) -> None:
        """Resamples the population according to member fitness."""
        new_pop = list(self._get_best_n())
        self._repopulate(new_pop)
        self._apply_mutations(new_pop)
        self._pop = new_pop
        self.zero_ratings()

    def _get_best_n(self) -> Iterable[Candidate]:
        # XXX could this be made faster with quick select?
        sorted_cands = sorted(self._pop,
                              key=lambda cand: cand.fitness,
                              reverse=True)
        best_n = int(self._ga_params.best_n_frac * self._pop_size)
        for c, _ in sorted_cands[:best_n]:
            yield c

    def _repopulate(self, new_pop: List[Candidate]) -> None:
        fitness_probs = softmax([c.fitness for c in self._pop])
        while len(new_pop) < self._pop_size:
            mother, father = np.random.choice(self._pop, size=2, p=fitness_probs)
            new_pop.append(mother.crossover(father))

    def _apply_mutations(self, new_pop: List[Candidate]) -> None:
        num_to_mutate = int(self._ga_params.mutation_frac * self._pop_size)
        for _ in range(num_to_mutate):
            mutate_ind = np.random.choice(self._pop_size)
            cand_to_mutate = new_pop[mutate_ind]
            new_pop[mutate_ind] = cand_to_mutate.mutate()

    def __iter__(self):
        self._cur = 0
        return self

    def __next__(self):
        if self._cur >= len(self._pop):
            raise StopIteration
        next_cand = self._pop[self._cur]
        self._cur += 1
        return next_cand

class Trainer(ABC):
    """Implements model training loop."""

    def __init__(self, 
                 pop_size: int,
                 layer_lengths: List[int],
                 ga_params: GenAlgParams):
        self._pop_size = pop_size
        self._layer_lengths = layer_lengths
        self._ga_params = ga_params
        self._iterations = 0

    def train(self) -> Population:
        pop = Population(
                self._pop_size,
                self._layer_lengths,
                self._ga_params
            )
        num_seen = 0
        while not self._is_converged():
            pop.zero_ratings()
            for level in LevelTraversal():
                pop.process_level(level)
                num_seen += len(level)
                if num_seen >= self._ga_params.resample_after:
                    pop.resample()
                    num_seen = 0
        return pop

    def _is_converged(self) -> bool:
        self._iterations += 1
        return self._iterations > 100
