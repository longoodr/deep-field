import numpy as np
import pytest

from deepfield.model.ratings import PlayerRatings


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
