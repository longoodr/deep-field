from typing import Tuple

import pytest

from deepfield.enums import Outcome
from deepfield.playgraph.retrieval import PlayGraphPersistor

from tests import utils

STRIKEOUT = Outcome.STRIKEOUT
LINEOUT = Outcome.LINEOUT
GROUNDOUT = Outcome.GROUNDOUT
FLYOUT = Outcome.FLYOUT
WALK = Outcome.WALK
SINGLE = Outcome.SINGLE
DOUBLE = Outcome.DOUBLE
TRIPLE = Outcome.TRIPLE
HOMERUN = Outcome.HOMERUN

pairs = [
    ("Single", SINGLE),
    ("Double", DOUBLE),
    ("Triple", TRIPLE),
    ("Home Run", HOMERUN),
    ("Flyball", FLYOUT),
    ("Popfly", FLYOUT),
    ("Pop Fly", FLYOUT),
    ("Lineout", LINEOUT),
    ("Groundout", GROUNDOUT),
    ("Bunt Ground Ball Double Play: Bunt 1B-3B-2B (Front of Home)", GROUNDOUT),
    ("Double Play: Fielder's Choice P; Conforto out at Hm/P-3B-C; Alonso out at 3B/C-3B", None),
    ("Balk; Walker to 2B", None),
    ("Defensive Indifference; Walker to 2B", None),
    ("Fielder's Choice 2B; Walker to 3B; Flores to 2B", None),
    ("Hit By Pitch; Walker to 2B", None),
    ("Passed Ball; Castro to 3B; Walker to 2B", None),
    ("Wild Pitch; Marte to 3B; Walker to 2B", None),
    ("Walker Steals 2B", None),
    ("Walker Caught Stealing", None),
    ("Double Play: Strikeout Swinging, Parra Caught Stealing 2B (C-2B)", STRIKEOUT),
    ("Double Play: Groundout: 3B-2B/Forceout at 3B", GROUNDOUT),
    ("Ground Ball Double Play: 2B-SS-1B", GROUNDOUT),
    ("Double Play: Strikeout Swinging, Walker Caught Stealing 2B (C-2B)", STRIKEOUT),
    ("Ground-rule Double (Fly Ball to Deep RF Line); Peralta Scores; Walker to 3B", DOUBLE),
    ("Intentional Walk", WALK),
    ("Walk", WALK),
    ("Walker Picked off 1B (E1); Walker to 2B", None),
    ("Double Play", None),
    ("Double Play: Strikeout, Reyes Picked off 3B (C-3B)", STRIKEOUT),
    ("Walker Picked off 3B (C-3B)", None),
    ("Baserunner Advance; Ahmed to 2B", None),
    ("Baserunner Out Advancing; Winker out at 2B/C-SS", None),
    ("Bunt Groundout", GROUNDOUT),
    ("Bunt Popfly", FLYOUT),
    ("Double to CF (Line Drive to Deep CF-RF)", DOUBLE),
    ("Reached on E5 (Pop Fly to P's Right)", FLYOUT),
    ("Reached on E5 (throw) (Ground Ball to SS-3B Hole); Gurriel to 2B", GROUNDOUT),
    ("Reached on E6 (Line Drive to Deep SS-2B)", LINEOUT),
    ("Reached on Interference on C", None)
]

@pytest.mark.parametrize("pair", pairs)
def test_outcomes(pair: Tuple[str, Outcome]):
    desc, outcome = pair
    assert Outcome.from_desc(desc) == outcome

def test_percentages():
    utils.init_test_env()
    with pytest.raises(RuntimeError):
        Outcome.get_percentages()
    utils.insert_cubs_game()
    PlayGraphPersistor().ensure_consistency()
    p = Outcome.get_percentages()
    pass
    