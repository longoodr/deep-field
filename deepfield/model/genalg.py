from abc import ABC, abstractmethod
from typing import List, Tuple

import networkx as nx

from deepfield.model.ratings import PlayerRatings, PredictionModel
from deepfield.model.transition import TransitionGenotype
from deepfield.playgraph.graph import MaximalAntichainLattice

"""
(Parametrized by:
    Population size,
    Prediction model structure,
    Number of maximal antichains before resample
)
Generate initial population
While not converged:
    For each (prediction model, transition function, player ratings) tuple:
        Reset player ratings
    For each maximal antichain in maximal antichain lattice:
        For each (prediction model, transition function, player ratings) tuple:
            Backprop prediction model against actual outcome distributions in maximal antichain
            For each play in maximal antichain:
                Use prediction model to compute KL divergence between actual and expected outcomes for each play
                Add KL divergence to transition function loss (lower loss => more fit)
                Compute transition function unit vector from play outcome
                Scale vector by KL divergence
                Update player ratings by scaled vector
        If time to resample:
            Resample population
"""

class Trainer(ABC):
    """Implements model training loop."""

    _Candidate = Tuple[PredictionModel, TransitionGenotype, PlayerRatings]

    def __init__(self,
                 graph: nx.DiGraph,
                 pop_size: int,
                 num_stats: int):
        self._lattice = MaximalAntichainLattice(graph)
        self._pop_size = pop_size
        self._num_stats = num_stats

    def train(self):
        self._population = self._generate_inital_population()
        while not self._is_converged():
            for antichain in self._lattice:
                for member in self._population:
                    pass

    def _generate_inital_population(self) -> List[self._Candidate]:
        return [(
                self._generate_initial_prediction_model(),
                self._generate_initial_transition_genotype(),
                PlayerRatings(self._num_stats)
            ) for _ in range(self._pop_size)]
    
    @abstractmethod
    def _generate_initial_prediction_model(self) -> PredictionModel:
        pass

    @abstractmethod
    def _generate_initial_transition_genotype(self) -> TransitionGenotype:
        pass

    @abstractmethod
    def _is_converged(self):
        pass
