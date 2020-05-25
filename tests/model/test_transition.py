import pytest

from deepfield.enums import Outcome
from deepfield.model.transition import TransitionGenotype


class TestTransitionGenotype:

    def test_access(self):
        g = TransitionGenotype.get_random_genotype(3)
        for o in Outcome:
            val = o.value
            assert g._vecs[val] is g[val]
            assert g._vecs[val] is g[o]
            

    def test_mutation(self):
        pass

    def test_crossover(self):
        pass