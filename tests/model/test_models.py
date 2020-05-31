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