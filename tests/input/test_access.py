import numpy as np
from keras.utils import to_categorical

from deepfield.dbmodels import get_data_name
from deepfield.enums import Outcome
from deepfield.input.reading import ReadableDatafile
from deepfield.input.writing import InputDataPersistor
from tests import utils


def setup_module(_):
    utils.init_test_env()
    np.random.seed(1)

def teardown_module(_):
    utils.remove_files()
    np.random.seed(None)

class TestDatafile:

    LEN = 90
    df: ReadableDatafile

    @classmethod
    def setup_class(cls):
        utils.insert_natls_game()
        InputDataPersistor().ensure_consistency()
        cls.df = ReadableDatafile(get_data_name())

    @classmethod
    def teardown_class(cls):
        cls.df.close()

    def test_access(self):
        assert self.df.x.shape[0] == self.LEN
        assert self.df.y.shape[0] == self.LEN
        assert (self.df.y[0] == to_categorical(Outcome.DOUBLE.value, len(Outcome))).all()
        assert (self.df.y[1] == to_categorical(Outcome.STRIKEOUT.value, len(Outcome))).all()

    def test_indices(self):
        train, test = self.df.get_train_test_ids(1)
        for i in range(self.LEN):
            assert ((i in train and i not in test) !=
                (i in test and i not in train))