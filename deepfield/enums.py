from collections import Counter
from enum import Enum, IntFlag
from typing import Counter as CounterType
from typing import Optional

import numpy as np
from peewee import fn as fn

from deepfield.dbmodels import Play


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
    dependent on the field configuration should be ignored, like fielder's 
    choices. This also means that errors should be treated as outs, because the
    errors are due to the fielder and would have otherwise been an out.
    """

    """
    XXX Should these include wild pitches / hit by pitches? Those plays are
    technically field agnostic...

    XXX How should bunts be considered? Some are field-dependent but others
    aren't...
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
        return _OutcomePercentageTracker.get_percentages()

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

class _OutcomePercentageTracker:

    _percs: np.ndarray = None

    _SAMPLE_OVER = 50000

    @classmethod
    def get_percentages(cls) -> np.ndarray:
        if cls._percs is not None:
            return cls._percs
        query = cls._random_sample()
        if query.count() == 0:
            raise RuntimeError("No plays in database")
        ctr: CounterType[int] = Counter()
        for (desc,) in query.iterator():
            outcome = Outcome.from_desc(desc)
            if outcome is None:
                continue
            ctr[outcome.value] += 1
        cnts = np.asarray([ctr[i] for i in range(len(Outcome))])
        cls._percs = cnts / np.sum(cnts)
        return cls._percs

    @classmethod
    def _random_sample(cls):
        return (Play.select(Play.desc)
                .order_by(fn.Random())
                .limit(cls._SAMPLE_OVER)
                .tuples()
            )
        