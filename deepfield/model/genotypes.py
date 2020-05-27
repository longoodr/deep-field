from abc import ABC, abstractmethod
from typing import Dict, Iterable, List

import numpy as np
from tensorflow.keras import backend as K
from tensorflow.keras.layers import Activation, Dense, Flatten, InputLayer
from tensorflow.keras.losses import kullback_leibler_divergence as kl_div
from tensorflow.keras.models import Model, Sequential, clone_model
from tensorflow.keras.utils import to_categorical

from deepfield.enums import Outcome


class Mateable(ABC):
    """A point in a parameter space which can be crossed with a mate."""

    @abstractmethod
    def crossover(self, mate):
        """Returns two children that result when crossed with the given mate."""
        pass

    def _random_parent(self, mate):
        return self if np.random.uniform < 0.5 else mate

class Copyable(ABC):
    
    @abstractmethod
    def copy(self):
        pass

class RandomlyChooseParent(Mateable, Copyable):
    """When mated, will return copies of parents, chosen at random."""

    def crossover(self, mate):
        for _ in range(2):
            yield self._random_parent(mate).copy()

class Genotype(Mateable, Copyable):
    """A point in a parameter space which can be subjected to genetic algorithm
    optimization.
    """

    @abstractmethod
    def get_mutated(self):
        """Returns a mutated copy of this Genotype."""
        pass

class Candidate(Genotype):
    """A candidate set of models used by the Trainer."""

    def __init__(self, 
                 pm: PredictionModel, 
                 tg: TransitionFunction, 
                 pr: PlayerRatings):
        self.pred_model = pm
        self.trans_geno = tg
        self.ratings = pr
        self.fitness = 0

    @classmethod
    def get_initial(cls, num_stats: int, layer_lengths: List[int])\
            -> "Candidate":
        """Returns a random candidate."""
        pm = KerasPredictionModel.from_params(num_stats, layer_lengths)
        tg = TransitionFunction.get_random_genotype(num_stats)
        pr = PlayerRatings(num_stats)
        return Candidate(pm, tg, pr)

class PredictionModel(RandomlyChooseParent):
    """A model which predicts outcome distributions from player stat pairwise
    differences.
    """

    @abstractmethod
    def backprop(self, pairwise_diffs: np.ndarray, outcomes: np.ndarray)\
            -> np.ndarray:
        """Performs backpropagation using the pairwise diffs as input and
        outcomes as output. Returns the KL-divergence between each expected and
        actual outcome distribution after backpropagation is performed.
        """
        pass
        
    @abstractmethod
    def predict(self, pairwise_diffs: np.ndarray) -> np.ndarray:
        """Returns the predicted probability distribution for the given 
        pairwise differences.
        """
        pass

class KerasPredictionModel(PredictionModel):
    """A prediction model backed by a Keras NN."""

    @classmethod
    def from_params(cls, num_stats: int, layer_lengths: List[int])\
            -> "KerasPredictionModel":
        m = Sequential()
        m.add(InputLayer((num_stats, num_stats,)))
        m.add(Flatten())
        for num_units in layer_lengths:
            m.add(Dense(num_units, activation="relu"))
        m.add(Dense(len(Outcome)))
        m.add(Activation("softmax"))
        m.compile("adam", loss=kl_div)
        return cls(m)

    def __init__(self, model: Model):
        self._model = model

    def backprop(self, pairwise_diffs: np.ndarray, outcomes: np.ndarray)\
            -> np.ndarray:
        y = to_categorical(outcomes, num_classes=len(Outcome))
        self._model.train_on_batch(pairwise_diffs, y)
        predictions = self.predict(pairwise_diffs)
        return K.eval(kl_div(K.variable(y), self._model(pairwise_diffs)))

    def predict(self, pairwise_diffs: np.ndarray) -> np.ndarray:
        return K.eval(self._model(pairwise_diffs))

    def crossover(self, mate: "KerasPredictionModel") -> "KerasPredictionModel":
        return self._random_parent(mate).copy()

    def copy(self) -> "KerasPredictionModel":
        copied_model = clone_model(self._model)
        return KerasPredictionModel(copied_model)

class TransitionFunction(Genotype):
    """A genotype for the transition function of a rating system."""

    def __init__(self, vecs: np.ndarray):
        self._vecs = vecs

    def __getitem__(self, outcome: int) -> np.ndarray:
        return self._vecs[outcome]

    def crossover(self, mate: "TransitionFunction")\
            -> Iterable["TransitionFunction"]:
        """Returns children of this genotype when reproducing with the given
        mate.
        
        Two children are produced. For the first child, a random parent is
        selected for each outcome, and the child inherits the associated
        outcome vector from its parent for that outcome. The second child
        receives the outcome vector from the unselected parent for that
        outcome.
        """
        for _ in range(2):
            vec_parents = [self._random_parent(mate)
                    for _ in range(len(self._vecs))]
            child_vecs = [parent._vecs[i] for i, parent in enumerate(vec_parents)]
            yield TransitionFunction(child_vecs)

    def get_mutated(self, rate: float = 0.1) -> "TransitionFunction":
        """Returns a mutated version of this TransitionFunction.
        
        To mutate, a random entry in a random vector is slightly perturbed, and
        then the mutated vector is normalized.
        """
        mutated_vecs = [np.copy(v) for v in self._vecs]
        vec_to_mutate = mutated_vecs[np.random.randint(0, len(self._vecs))]
        vec_entry_to_mutate = np.random.randint(0, vec_to_mutate.size)
        old_val = vec_to_mutate[vec_entry_to_mutate]
        # note new_val still has mean 0, variance 1
        new_val = (1 - rate) * old_val + rate * np.random.standard_normal()
        vec_to_mutate[vec_entry_to_mutate] = new_val
        vec_to_mutate /= np.linalg.norm(vec_to_mutate)
        return TransitionFunction(mutated_vecs)

    @classmethod
    def get_random_genotype(cls, num_stats: int) -> "TransitionFunction":
        vecs = np.asarray([cls.rand_unit_sphere_vec(num_stats)
                           for _ in range(len(Outcome))])
        return TransitionFunction(vecs)

    @staticmethod
    def rand_unit_sphere_vec(dims: int) -> np.ndarray:
        """Returns a random vector on the unit sphere in the given number of
        dimensions.
        """
        x = np.random.standard_normal(dims)
        return x / np.linalg.norm(x)

class PlayerRatings(RandomlyChooseParent):
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
