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
        self._top_n = int(self._ga_params.best_n_frac * self._pop_size)
        self._pool = self._create_model
        self._pop = [
                {
                    "pred_model": self._create_model(),
                    "trans_func": TransitionFunction \
                            .get_initial(ga_params.num_stats),
                    "ratings": PlayerRatings(ga_params.num_stats),
                    "fitness": 0
                }
                for _ in range(pop_size)
            ]

    def _create_model(self) -> Model:
        m = Sequential()
        num_stats = self._ga_params.num_stats
        m.add(InputLayer((num_stats, num_stats,)))
        m.add(Flatten())
        for num_units in self._layer_lengths:
            m.add(Dense(num_units, activation="relu"))
        m.add(Dense(len(Outcome)))
        m.add(Activation("softmax"))
        m.compile("adam", kl_div)
        return PredictionModel(m)

    def zero_ratings(self) -> None:
        for cand in self._pop:
            cand["fitness"] = 0

    def process_level(self, level: List[Dict[str, int]]) -> None:
        """Backprops the level data for each candidate and updates ratings."""
        outcomes = np.asarray([n["outcome"] for n in level])
        one_hots = to_categorical(outcomes, num_classes=len(Outcome))
        y = Batcher.pad_batch(one_hots)
        for cand in self:
            diffs = cand["ratings"].get_node_pairwise_diffs(level)
            x = Batcher.pad_batch(diffs)
            weights = Batcher.get_padded_weights(diffs.shape[0])
            kl_divs = cand["pred_model"].backprop(x, y, weights)
            tot_kl_div = np.sum(kl_divs)
            cand["fitness"] += 1 / tot_kl_div  # less kl_div implies more fit
            for i, node in enumerate(level):
                delta = cand["trans_func"][node["outcome"]] * kl_divs[i]
                cand["ratings"].update(delta, node["batter_id"], node["pitcher_id"])

    def resample(self) -> None:
        """Performs genetic algorithm optimization on the population."""
        most_fit_indices = self._get_most_fit_indices()
        old_trans_funcs = [cand["trans_func"] for cand in self._pop]
        old_weights = [cand["pred_model"].model.get_weights() for cand in self._pop]
        fitness_probs = softmax([cand["fitness"] for cand in self._pop])
        for i, cand in enumerate(self._pop):
            if i in most_fit_indices:
                continue
            trans_mother, trans_father = np.random.choice(
                    old_trans_funcs,
                    size=2,
                    replace=False,
                    p=fitness_probs
                )
            trans_child = trans_mother.crossover(trans_father) # so progressive!
            if (np.random.uniform() < self._ga_params.mutation_frac):
                trans_child.mutate()
            cand["trans_func"] = trans_child
            weight_ind = np.random.choice(len(old_weights), p=fitness_probs)
            cand["pred_model"].model.set_weights(old_weights[weight_ind])
            cand["ratings"].reset()
        self.zero_ratings()
        
    def _get_most_fit_indices(self) -> Set[int]:
        """Returns the indices of the most fit candidates in the population."""
        pop_w_indices = [(i, cand) for i, cand in enumerate(self._pop)]
        sorted_by_fitness = sorted(
                pop_w_indices,
                key=lambda x: x[1]["fitness"],
                reverse=True
            )
        return set([i for i, _ in sorted_by_fitness[:self._top_n]])

    def __iter__(self):
        self._cur = 0
        return self

    def __next__(self):
        if self._cur >= len(self._pop):
            raise StopIteration
        next_cand = self._pop[self._cur]
        self._cur += 1
        return next_cand

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
        self.model.train_on_batch(pairwise_diffs, outcomes, weights)
        return K.eval(kl_div(K.variable(outcomes), self.model(pairwise_diffs)))

    def predict(self, pairwise_diffs: np.ndarray) -> np.ndarray:
        return K.eval(self.model(pairwise_diffs))

class TransitionFunction:
    """A genotype for the transition function of a rating system."""

    def __init__(self, vecs: np.ndarray):
        self._vecs = vecs

    def __getitem__(self, outcome: int) -> np.ndarray:
        return self._vecs[outcome]

    def crossover(self, mate: "TransitionFunction") -> "TransitionFunction":
        """Returns a child when reproducing with the given mate."""
        parents = [self._random_parent(mate) for _ in range(len(self._vecs))]
        child_vecs = np.asarray([parent._vecs[i] for i, parent in enumerate(parents)])
        return TransitionFunction(child_vecs)

    def _random_parent(self, mate: "TransitionFunction") -> "TransitionFunction":
        return self if np.random.uniform() < 0.5 else mate

    def mutate(self, rate: float = 0.1) -> None:
        """To mutate, a random entry in a random vector is slightly perturbed, and
        then the mutated vector is normalized.
        """
        vec_to_mutate = self._vecs[np.random.randint(0, self._vecs.shape[0])]
        vec_entry_to_mutate = np.random.randint(0, vec_to_mutate.size)
        old_val = vec_to_mutate[vec_entry_to_mutate]
        # note new_val still has mean 0, variance 1
        new_val = (1 - rate) * old_val + rate * np.random.standard_normal()
        vec_to_mutate[vec_entry_to_mutate] = new_val
        vec_to_mutate /= np.linalg.norm(vec_to_mutate)

    @classmethod
    def get_initial(cls, num_stats: int) -> "TransitionFunction":
        vecs = np.asarray([cls._rand_unit_sphere_vec(num_stats)
                           for _ in range(len(Outcome))])
        return TransitionFunction(vecs)

    @staticmethod
    def _rand_unit_sphere_vec(dims: int) -> np.ndarray:
        """Returns a random vector on the unit sphere in the given number of
        dimensions.
        """
        x = np.random.standard_normal(dims)
        return x / np.linalg.norm(x)

    def __eq__(self, other):
        return (self.__class__ == other.__class__
                and (self._vecs == other._vecs).all()
            )

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
