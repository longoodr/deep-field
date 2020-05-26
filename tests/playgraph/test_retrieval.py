from typing import Iterable, Tuple

import networkx as nx
import pytest

from deepfield.dbmodels import Play
from deepfield.playgraph.retrieval import PlayGraphPersistor
from deepfield.scraping.bbref_pages import BBRefLink
from deepfield.scraping.nodes import ScrapeNode
from deepfield.scraping.pages import Page
from tests import utils


def setup_module(module):
    utils.init_test_env()

def teardown_module(module):
    utils.delete_db_file()

class TestPersistence:

    @classmethod
    def setup_class(cls):
        utils.clean_db()

def _play_num_to_id(play_num: int) -> int:
    return Play.get(Play.play_num == play_num).id

def _play_nums_to_id(play_nums: Tuple) -> Tuple:
    return tuple([_play_num_to_id(pnum) for pnum in play_nums])