import numpy as np
import pytest

from deepfield.enums import Outcome
from deepfield.model.models import Batcher, PlayerRatings, PredictionModel


def setup_module(_):
    np.random.seed(1)

def teardown_module(_):
    np.random.seed(None)

class TestBatcher:

    def test_no_pad_needed(self):
        for sample_shape in [(2,), (3, 2), (4, 3, 6)]:
            batch_size = Batcher.PAD_SIZE
            batch = np.ones((batch_size, *sample_shape))
            padded_batch = Batcher.pad_batch(batch)
            padded_weights = Batcher.get_padded_weights(batch_size)
            assert (padded_batch == batch).all()
            assert (padded_weights == np.ones(batch_size)).all()
            batch_size *= 2

    def test_pad(self):
        for sample_shape in [(2,), (3, 2), (4, 3, 6)]:
            for batch_size in range(33, 64, 5):
                batch = np.ones((batch_size, *sample_shape))
                pad_length = 64 - batch_size
                padded_batch = Batcher.pad_batch(batch)
                padded_weights = Batcher.get_padded_weights(batch_size)
                expected_batch = \
                        np.concatenate([batch, np.zeros((pad_length, *sample_shape))])
                expected_weights = \
                        np.concatenate([np.ones(batch_size), np.zeros(pad_length)])
                assert (padded_batch == expected_batch).all()
                assert (padded_weights == expected_weights).all()

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
            pr.update(-1 * delta, 0, 1)
            assert (pr.get_batter_rating(0) == zero).all()
            assert (pr.get_pitcher_rating(1) == zero).all()

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
