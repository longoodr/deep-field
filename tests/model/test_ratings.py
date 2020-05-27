import numpy as np
import pytest

from deepfield.enums import Outcome
from deepfield.model.ratings import KerasPredictionModel, PlayerRatings


class TestPredictionModel:

    def test_backprop(self):
        seen_out = Outcome.STRIKEOUT.value
        for num_stats in range(3, 6):
            m = KerasPredictionModel(num_stats, [6, 6])
            pdiffs = np.asarray([PlayerRatings(num_stats).get_pairwise_diffs(0, 0)])
            outcomes = np.asarray([seen_out])
            kl_div = m.backprop(pdiffs, outcomes)
            p1 = m.predict(pdiffs)
            # backprop should reduce kl_div after 2nd session
            kl_div2 = m.backprop(pdiffs, outcomes)
            assert kl_div > kl_div2
            p2 = m.predict(pdiffs)
            # seen outcome probability should be higher after backprop
            assert p2[0,seen_out] > p1[0,seen_out]

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
            for r in [pr, cp]:
                assert (r.get_batter_rating(0) == delta).all()
                assert (r.get_pitcher_rating(1) == -1 * delta).all()
            pr.update(delta, 0, 1)
            assert (pr.get_batter_rating(0) == 2 * delta).all()
            assert (pr.get_pitcher_rating(1) == -2 * delta).all()
            assert (cp.get_batter_rating(0) == delta).all()
            assert (cp.get_pitcher_rating(1) == -1 * delta).all()

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
