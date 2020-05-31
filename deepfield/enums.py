from enum import Enum, IntFlag
from typing import Optional

import numpy as np
from peewee import fn as fn

from deepfield.dbmodels import PlayNode


class TimeOfDay(Enum):
    DAY = 0
    NIGHT = 1
    
class FieldType(Enum):
    TURF = 0
    GRASS = 1
    
class Handedness(Enum):
    LEFT = 0
    RIGHT = 1
    BOTH = 2
    
class InningHalf(Enum):
    TOP = 0
    BTM = 1

class OnBase(IntFlag):
    EMPTY = 0
    FIRST = 1
    SECOND = 2
    THIRD = 4

class Outcome(Enum):
    """Field agnostic outcomes for plays. "Field agnostic" means that outcomes
    dependent on the field configuration should be ignored: for example, bunts.
    This also means that errors should be treated as outs, because the errors
    are due to the fielder and would have otherwise been an out.
    """

    """XXX Should these include wild pitches / hit by pitches? Those plays are
    technically field agnostic...
    """

    STRIKEOUT = 0
    LINEOUT = 1
    GROUNDOUT = 2
    FLYOUT = 3
    WALK = 4
    SINGLE = 5
    DOUBLE = 6
    TRIPLE = 7
    HOMERUN = 8

    @classmethod
    def get_percentages(cls) -> np.ndarray:
        """Returns an array containing the percentages corresponding to the
        occurrence rate of each outcome in the database.
        """
        query = (PlayNode.select(
                PlayNode.outcome,
                fn.count(PlayNode.outcome).alias("cnt")
                ).group_by(PlayNode.outcome)
                .namedtuples()
            )
        present_outcomes_to_cnt = {r.outcome: r.cnt for r in query}
        # fill outcomes that didn't occur with 0
        cnts = np.asarray([
                0 if outcome not in present_outcomes_to_cnt
                else present_outcomes_to_cnt[outcome]
                for outcome in range(len(cls))
            ])
        if np.sum(cnts) == 0:
            raise RuntimeError("No plays in database")
        percentages = cnts / np.sum(cnts)
        return percentages

    @classmethod
    def from_desc(cls, desc: str) -> Optional["Outcome"]:
        """Converts a description to an Outcome, or returns None if this
        description can't be matched to one.
        """
        desc = desc.lower().split(";")[0]
        if "double play" in desc or "triple play" in desc:
            return cls._parse_dbl_trpl_plays(desc)
        if "reached on" in desc:
            return cls._parse_error(desc)
        if "steal" in desc:
            return None
        if "picked off" in desc:
            return None
        if "single" in desc:
            return cls.SINGLE
        if "double" in desc:
            return cls.DOUBLE
        if "triple" in desc:
            return cls.TRIPLE
        if "home run" in desc:
            return cls.HOMERUN
        if "strikeout" in desc:
            return cls.STRIKEOUT
        if "lineout" in desc:
            return cls.LINEOUT
        if "fly" in desc:
            return cls.FLYOUT
        if "on foul ball" in desc:
            # foul ball error: treat error as out
            return cls.FLYOUT
        if "groundout" in desc:
            return cls.GROUNDOUT
        if "walk" in desc:
            return cls.WALK
        return None

    @classmethod
    def _parse_dbl_trpl_plays(cls, desc: str) -> Optional["Outcome"]:
        if "strikeout" in desc:
            return cls.STRIKEOUT
        if "ground ball" in desc or "groundout" in desc:
            return cls.GROUNDOUT
        if "lineout" in desc:
            return cls.LINEOUT
        if "fly" in desc:
            return cls.FLYOUT
        return None

    @classmethod
    def _parse_error(cls, desc: str) -> Optional["Outcome"]:
        # in the interest of being field-agnostic, treat errors as outs
        if "ground ball" in desc:
            return cls.GROUNDOUT
        if "fly" in desc:
            return cls.FLYOUT
        if "line" in desc:
            return cls.LINEOUT
        return None
