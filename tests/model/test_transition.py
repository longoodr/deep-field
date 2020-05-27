import numpy as np
import pytest

from deepfield.enums import Outcome
from deepfield.model.transition import TransitionFunction


class TestTransitionFunction:

    def test_access(self):
        for num_stats in range(3, 6):
            g = TransitionFunction.get_random_genotype(num_stats)
            for o in Outcome:
                val = o.value
                assert (g._vecs[val] == g[val]).all()
            
    def test_mutation(self):
        for num_stats in range(3, 6):
            g = TransitionFunction.get_random_genotype(num_stats)
            m = g.get_mutated()
            num_diff = 0
            for gvec, mvec in zip(g._vecs, m._vecs):
                for ge, me in zip(gvec, mvec):
                    if ge != me:
                        num_diff += 1
            assert num_diff == num_stats

    def test_crossover(self):
        for num_stats in range(3, 6):
            a = TransitionFunction.get_random_genotype(num_stats)
            b = TransitionFunction.get_random_genotype(num_stats)
            c1, c2 = a.get_children(b)
            parent_vecs = a._vecs + b._vecs
            for vc1, vc2 in zip(c1._vecs, c2._vecs):
                for evc1, evc2 in zip(vc1, vc2):
                    assert evc1 != evc2
                assert np.any((vc1 == x).all() for x in parent_vecs)
                assert np.any((vc2 == x).all() for x in parent_vecs)