from tests import utils

import pytest

def setup_module(module):
    utils.init_test_env()

def teardown_module(module):
    utils.delete_db_file()

class TestTraversal:
    pass