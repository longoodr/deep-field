import numpy as np
import pytest

from deepfield.enums import Outcome
from deepfield.model.genotypes import (Candidate, KerasPredictionModel,
                                       PlayerRatings, TransitionFunction)


class TestCandidate:

    def test_mutation(self):
        for num_stats in range(3, 6):
            c = Candidate.get_initial(num_stats, [6, 6])
            m = c.get_mutated()
            assert c != m
            assert c.pred_model == m.pred_model
            assert c.trans_func != m.trans_func
            assert c.ratings == m.ratings

class TestTransitionFunction:

    def test_access(self):
        for num_stats in range(3, 6):
            g = TransitionFunction.get_initial(num_stats)
            for o in Outcome:
                val = o.value
                assert (g._vecs[val] == g[val]).all()
            
    def test_mutation(self):
        for num_stats in range(3, 6):
            g = TransitionFunction.get_initial(num_stats)
            m = g.get_mutated()
            num_diff = 0
            for gvec, mvec in zip(g._vecs, m._vecs):
                for ge, me in zip(gvec, mvec):
                    if ge != me:
                        num_diff += 1
            assert num_diff == num_stats

    def test_crossover(self):
        for num_stats in range(3, 6):
            a = TransitionFunction.get_initial(num_stats)
            b = TransitionFunction.get_initial(num_stats)
            c1, c2 = a.crossover(b)
            parent_vecs = a._vecs + b._vecs
            for vc1, vc2 in zip(c1._vecs, c2._vecs):
                for evc1, evc2 in zip(vc1, vc2):
                    assert evc1 != evc2
                assert np.any((vc1 == x).all() for x in parent_vecs)
                assert np.any((vc2 == x).all() for x in parent_vecs)

    def test_copy(self):
        for num_stats in range(3, 6):
            a = TransitionFunction.get_initial(num_stats)
            b = a.copy()
            assert a is not b
            assert a == b
            b._vecs[0] *= 2
            assert a != b

class TestPredictionModel:

    def test_backprop(self):
        seen_out = Outcome.STRIKEOUT.value
        for num_stats in range(3, 6):
            m = KerasPredictionModel.from_params(num_stats, [6, 6])
            pdiffs, outcomes = self._get_basic_data(num_stats, seen_out)
            kl_div = m.backprop(pdiffs, outcomes)
            p1 = m.predict(pdiffs)
            # backprop should reduce kl_div after 2nd session
            kl_div2 = m.backprop(pdiffs, outcomes)
            assert kl_div > kl_div2
            p2 = m.predict(pdiffs)
            # seen outcome probability should be higher after backprop
            assert p2[0,seen_out] > p1[0,seen_out]

    def test_crossover(self):
        for num_stats in range(3, 6):
            a = KerasPredictionModel.from_params(num_stats, [6, 6])
            b = KerasPredictionModel.from_params(num_stats, [6, 6])
            assert a != b
            children = a.crossover(b)
            for c in children:
                assert c == a or c == b
                assert c is not a or c is not b

    def test_copy(self):
        seen_out = Outcome.STRIKEOUT.value
        for num_stats in range(3, 6):
            a = KerasPredictionModel.from_params(num_stats, [6, 6])
            b = a.copy()
            assert a == b
            assert a is not b
            pdiffs, outcomes = self._get_basic_data(num_stats, seen_out)
            b.backprop(pdiffs, outcomes)
            assert a != b

    @staticmethod
    def _get_basic_data(num_stats: int, seen_out: int):
        pdiffs = np.asarray([PlayerRatings(num_stats).get_pairwise_diffs(0, 0)])
        outcomes = np.asarray([seen_out])
        return pdiffs, outcomes

class TestPlayerRatings:

    def test_update_access(self):
        for num_stats in range(3, 6):
            pr = PlayerRatings(num_stats)
            zero = np.zeros(num_stats)
            assert (pr.get_batter_rating(0) == zero).all()
            assert (pr.get_pitcher_rating(1) == zero).all()
            delta = np.asarray([((i % 2) * 2) - 1 for i in range(num_stats)])
            pr.update(delta, 0, 1)
            assert (pr.get_batter_rating(0) == delta).all()
            assert (pr.get_batter_rating(1) == zero).all()
            assert (pr.get_pitcher_rating(0) == zero).all()
            assert (pr.get_pitcher_rating(1) == -1 * delta).all()

    def test_reset(self):
        for num_stats in range(3, 6):
            pr = PlayerRatings(num_stats)
            delta = np.ones(num_stats)
            for i in range(5):
                pr.update(delta, i, i)
            pr.reset()
            zero = np.zeros(num_stats)
            for i in range(5):
                assert (pr.get_batter_rating(i) == zero).all()
                assert (pr.get_pitcher_rating(i) == zero).all()

    def test_copy(self):
        for num_stats in range(3, 6):
            pr = PlayerRatings(num_stats)
            delta = np.ones(num_stats)
            pr.update(delta, 0, 1)
            cp = pr.copy()
            assert cp is not pr
            assert cp == pr
            for r in [pr, cp]:
                assert (r.get_batter_rating(0) == delta).all()
                assert (r.get_pitcher_rating(1) == -1 * delta).all()
            pr.update(delta, 0, 1)
            assert (pr.get_batter_rating(0) == 2 * delta).all()
            assert (pr.get_pitcher_rating(1) == -2 * delta).all()
            assert (cp.get_batter_rating(0) == delta).all()
            assert (cp.get_pitcher_rating(1) == -1 * delta).all()
            assert cp != pr

    def test_pdiffs(self):
        for num_stats in range(3, 6):
            pr = PlayerRatings(num_stats)
            should_be_zero = pr.get_pairwise_diffs(0, 0)
            assert (should_be_zero == np.zeros((num_stats, num_stats))).all()
            delta = np.arange(num_stats)
            pr.update(delta, 0, 1)
            pdiffs = pr.get_pairwise_diffs(0, 1)
            bat = pr.get_batter_rating(0)
            pit = pr.get_pitcher_rating(1)
            for i in range(num_stats):
                for j in range(num_stats):
                    assert (pdiffs[i,j] == bat[i] - pit[j])

    def test_crossover(self):
        for num_stats in range(3, 6):
            a = PlayerRatings(num_stats)
            b = PlayerRatings(num_stats)
            b.update(np.ones(num_stats), 0, 1)
            assert a != b
            children = a.crossover(b)
            for c in children:
                assert c == a or c == b
                assert c is not a and c is not b
