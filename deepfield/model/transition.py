from typing import List, Tuple, Union

import numpy as np

from deepfield.enums import Outcome


class TransitionGenotype:
    """A genotype for the transition function of a rating system."""

    def __init__(self, vecs: List[np.ndarray]):
        self._vecs = vecs

    def __getitem__(self, outcome: Union[Outcome, int]) -> np.ndarray:
        """Returns the unit vector associated with the given outcome."""
        if isinstance(outcome, int):
            return self._vecs[outcome]
        return self._vecs[outcome.value]

    def get_children(self, mate: "TransitionGenotype")\
            -> Tuple["TransitionGenotype", "TransitionGenotype"]:
        """Returns children of this genotype when reproducing with the given
        mate.
        
        Two children are produced. For the first child, a random parent is
        selected for each outcome, and the child inherits the associated
        outcome vector from its parent for that outcome. The second child
        receives the outcome vector from the unselected parent for that
        outcome.
        """
        child1_parents = [self if np.random.uniform() < 0.5 else mate
                                for _ in range(len(self._vecs))]
        child2_parents = [self if p == mate else mate for p in child1_parents]
        child1 = self._get_child(child1_parents)
        child2 = self._get_child(child2_parents)
        return (child1, child2,)

    @staticmethod 
    def _get_child(child_parents: List["TransitionGenotype"]) -> "TransitionGenotype":
        child_vecs = [parent._vecs[i] for i, parent in enumerate(child_parents)]
        return TransitionGenotype(child_vecs)

    def get_mutated(self, rate: float = 0.1) -> "TransitionGenotype":
        """Returns a mutated version of this TransitionGenotype.
        
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
        return TransitionGenotype(mutated_vecs)

    @classmethod
    def get_random_genotype(cls, num_stats: int) -> "TransitionGenotype":
        vecs = [cls.rand_unit_sphere_vec(num_stats) for _ in range(len(Outcome))]
        return TransitionGenotype(vecs)

    @staticmethod
    def rand_unit_sphere_vec(dims: int) -> np.ndarray:
        """Returns a random vector on the unit sphere in the given number of
        dimensions.
        """
        x = np.random.standard_normal(dims)
        return x / np.linalg.norm(x)
