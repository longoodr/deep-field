from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
from scipy.special import softmax

from deepfield.dbmodels import init_db
from deepfield.model.population import GenAlgParams, Population
from deepfield.playgraph.graph import LevelTraversal


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
                level = list(level)
                pop.process_level(level)
                num_seen += len(level)
                print(" ".join(
                            [f"{c['fitness']:.3f}" 
                            for c in sorted(list(pop)[:10],
                            key=lambda x: x["fitness"],
                            reverse=True)]),
                        f" {num_seen} of {self._ga_params.resample_after}"
                    )
                if num_seen >= self._ga_params.resample_after:
                    pop.resample()
                    num_seen = 0
        return pop

    def _is_converged(self) -> bool:
        self._iterations += 1
        return self._iterations > 100

init_db()
params = GenAlgParams(
        best_n_frac=0.2,
        mutation_frac=0.5,
        resample_after=2000,
        num_stats=4
    )
trainer = Trainer(5, [], params)
pop = trainer.train()
pass
