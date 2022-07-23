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
