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
        for num_stats in range(3, 6):
            g = TransitionGenotype.get_random_genotype(num_stats)
            m = g.get_mutated()
            num_diff = 0
            for gvec, mvec in zip(g._vecs, m._vecs):
                for ge, me in zip(gvec, mvec):
                    if ge != me:
                        num_diff += 1
            assert num_diff == num_stats

    def test_crossover(self):
        pass