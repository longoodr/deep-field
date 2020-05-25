import numpy as np
import pytest

from deepfield.model.ratings import PlayerRatings


class TestPlayerRatings:

    def test_copy(self):
        for num_stats in range(3, 6):
            pr = PlayerRatings(num_stats)
            delta = np.ones(num_stats)
            delta /= np.linalg.norm(delta)
            pr.update(delta, 0, 1)
            cp = pr.copy()
            assert (cp.get_batter_rating(0) == delta).all()
            pr.update(delta, 0, 1)
            assert (pr.get_batter_rating(0) == 2 * delta).all()
            assert (cp.get_batter_rating(0) == delta).all()
