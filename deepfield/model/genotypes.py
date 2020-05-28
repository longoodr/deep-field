from abc import ABC, abstractmethod
from typing import Dict, Iterable, List

import numpy as np
from tensorflow.keras import backend as K
from tensorflow.keras.layers import Activation, Dense, Flatten, InputLayer
from tensorflow.keras.losses import kullback_leibler_divergence as kl_div
from tensorflow.keras.models import Model, Sequential, clone_model
from tensorflow.keras.utils import to_categorical

from deepfield.enums import Outcome


class _Mateable(ABC):
    """A point in a parameter space which can be crossed with a mate."""

    @abstractmethod
    def crossover(self, mate):
        """Returns two children that result when crossed with the given mate."""
        pass

    def _random_parent(self, mate):
        return self if np.random.uniform() < 0.5 else mate

class _Copyable(ABC):

    @abstractmethod
    def copy(self):
        pass

class _RandomlyChooseParent(_Mateable, _Copyable):
    """When mated, will return two copies of parents, chosen at random."""

    def crossover(self, mate) -> Iterable:
        for _ in range(2):
            yield self._random_parent(mate).copy()

class _Genotype(_Mateable, _Copyable):
    """A point in a parameter space which can be subjected to genetic algorithm
    optimization.
    """

    @abstractmethod
    def get_mutated(self):
        """Returns a mutated copy of this Genotype."""
        pass

class Candidate(_Genotype):
    """A candidate set of models used by the Trainer."""

    def __init__(self, 
                 pm: "PredictionModel", 
                 tf: "TransitionFunction", 
                 pr: "PlayerRatings"):
        self.pred_model = pm
        self.trans_func = tf
        self.ratings = pr
        self.fitness = 0

    @classmethod
    def get_initial(cls, num_stats: int, layer_lengths: List[int])\
            -> "Candidate":
        """Returns a random candidate."""
        pm = NNetPredictionModel.from_params(num_stats, layer_lengths)
        tf = TransitionFunction.get_initial(num_stats)
        pr = PlayerRatings(num_stats)
        return Candidate(pm, tf, pr)

    def copy(self) -> "Candidate":
        pm = self.pred_model.copy()
        tf = self.trans_func.copy()
        pr = self.ratings.copy()
        return Candidate(pm, tf, pr)

    def crossover(self, mate: "Candidate") -> Iterable["Candidate"]:
        crossed_pms = self.pred_model.crossover(mate.pred_model)
        crossed_tfs = self.trans_func.crossover(mate.trans_func)
        crossed_prs = self.ratings.crossover(mate.ratings)
        for pm, tf, pr in zip(crossed_pms, crossed_tfs, crossed_prs):
            yield Candidate(pm, tf, pr)

    def get_mutated(self) -> "Candidate":
        pm = self.pred_model.copy()
        tf = self.trans_func.get_mutated()
        pr = self.ratings.copy()
        return Candidate(pm, tf, pr)

    def train_and_update(self, level: List[Dict[str, int]], outcomes: np.ndarray)\
            -> None:
        """Backprops against the level data and updates ratings."""
        diffs = self.ratings.get_node_pairwise_diffs(level)
        kl_divs = self.pred_model.backprop(diffs, outcomes)
        tot_kl_div = np.sum(kl_divs)
        self.fitness += 1 / tot_kl_div  # less kl_div implies more fit
        for i, node in enumerate(level):
            delta = self.trans_func[node["outcome"]] * kl_divs[i]
            self.ratings.update(delta, node["batter_id"], node["pitcher_id"])

    def __eq__(self, other):
        return (self.__class__ == other.__class__
                and self.pred_model == other.pred_model
                and self.trans_func == other.trans_func
                and self.ratings == other.ratings
            )

class PredictionModel(_RandomlyChooseParent):
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

class NNetPredictionModel(PredictionModel):
    """A prediction model backed by a Keras NN."""

    @classmethod
    def from_params(cls, num_stats: int, layer_lengths: List[int])\
            -> "NNetPredictionModel":
        m = Sequential()
        m.add(InputLayer((num_stats, num_stats,)))
        m.add(Flatten())
        for num_units in layer_lengths:
            m.add(Dense(num_units, activation="relu"))
        m.add(Dense(len(Outcome)))
        m.add(Activation("softmax"))
        cls._compile_model(m)
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

    def copy(self) -> "NNetPredictionModel":
        copied_model = clone_model(self._model)
        self._compile_model(copied_model)
        copied_model.set_weights(self._model.get_weights())
        return NNetPredictionModel(copied_model)

    def __eq__(self, other):
        input_layer_shape = self._model.get_layer(index=0).input_shape
        shape = tuple([1] + list(input_layer_shape)[1:])
        rand_input = np.random.random_sample(shape)
        self_out = self.predict(rand_input)
        other_out = other.predict(rand_input)
        return (self.__class__ == other.__class__
                and (self_out == other_out).all()
            )

    @staticmethod
    def _compile_model(model: Model):
        model.compile("adam", loss=kl_div)

class TransitionFunction(_Genotype):
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
        vec_parents = [self._random_parent(mate) for _ in range(len(self._vecs))]
        for parents in [vec_parents, [mate if p == self else self for p in vec_parents]]:
            child_vecs = np.asarray([parent._vecs[i] for i, parent in enumerate(parents)])
            yield TransitionFunction(child_vecs)

    def get_mutated(self, rate: float = 0.1) -> "TransitionFunction":
        """To mutate, a random entry in a random vector is slightly perturbed, and
        then the mutated vector is normalized.
        """
        cp = self.copy()
        vec_to_mutate = cp._vecs[np.random.randint(0, self._vecs.shape[0])]
        vec_entry_to_mutate = np.random.randint(0, vec_to_mutate.size)
        old_val = vec_to_mutate[vec_entry_to_mutate]
        # note new_val still has mean 0, variance 1
        new_val = (1 - rate) * old_val + rate * np.random.standard_normal()
        vec_to_mutate[vec_entry_to_mutate] = new_val
        vec_to_mutate /= np.linalg.norm(vec_to_mutate)
        return cp

    def copy(self) -> "TransitionFunction":
        return TransitionFunction(np.copy(self._vecs))

    @classmethod
    def get_initial(cls, num_stats: int) -> "TransitionFunction":
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

    def __eq__(self, other):
        return (self.__class__ == other.__class__
                and (self._vecs == other._vecs).all()
            )

class PlayerRatings(_RandomlyChooseParent):
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

    def __eq__(self, other):
        return (self.__class__ == other.__class__
                and self._ratings_eq(self._bratings, other._bratings)
                and self._ratings_eq(self._pratings, other._pratings)
            )
    
    @staticmethod
    def _ratings_eq(ratings1, ratings2) -> bool:
        if len(ratings1) != len(ratings2):
            return False
        return False not in [
                p1 == p2 and (r1 == r2).all() 
                for (p1, r1), (p2, r2)
                in zip(ratings1.items(), ratings2.items())
            ]