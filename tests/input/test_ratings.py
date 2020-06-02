import numpy as np
import pytest

from deepfield.dbmodels import Player
from deepfield.enums import Handedness, Outcome
from deepfield.input.ratings import HandednessTracker, PlayerRatings
from tests import utils


def setup_module(_):
    utils.init_test_env()

def teardown_module(_):
    utils.remove_files()

L = Handedness.LEFT.value
R = Handedness.RIGHT.value
B = Handedness.BOTH.value
hands = [
        ((L, L), (L, L)),
        ((L, R), (R, L)),
        ((R, L), (L, R)),
        ((R, R), (R, R)),
        ((B, L), (L, R)),
        ((B, R), (R, L)),
        ((L, B), (L, L)),
        ((R, B), (R, R)),
        ((B, B), (L, R))
    ]

@pytest.mark.parametrize("pair", hands)
def test_matchups(pair):
    matchup, exp = pair
    insert_batter(matchup[0])
    insert_pitcher(matchup[1])
    h = HandednessTracker()
    act = h.get_bat_pit_against_handednesses(1, 2)
    assert act == exp
    utils.clean_db()

class TestRatings:

    def test_diminishing(self):
        pass

    def test_handedness_updates(self):
        insert_batter(L)
        insert_pitcher(R)
        utils.insert_cubs_game()
        pr = PlayerRatings()
        outcome = Outcome.GROUNDOUT.value
        event_oh = np.asarray([1 if i == outcome else 0 for i in range(len(Outcome))])
        pr.update(1, 2, event_oh)
        percs = Outcome.get_percentages()
        for rating, hand in [
                (pr.get_batter(1), R),
                (pr.get_pitcher(2), L)
            ]:
            for subrating in rating._against_hand_subratings[hand]:
                assert ((subrating.rating > percs) == \
                        np.array([i == outcome for i in range(len(Outcome))])
                        ).all()

def insert_batter(bats):
    Player.create(**{
            "name": "George Burdell",
            "name_id": "burdege01",
            "bats": bats,
            "throws": Handedness.RIGHT.value,
        })

def insert_pitcher(throws):
    Player.create(**{
            "name": "George Burdell",
            "name_id": "burdege02",
            "bats": Handedness.RIGHT.value,
            "throws": throws
        })
