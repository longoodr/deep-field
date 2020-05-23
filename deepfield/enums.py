from enum import Enum, IntFlag
from typing import Optional


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
    def from_desc(cls, desc: str) -> Optional["Outcome"]:
        """Converts a description to an Outcome, or returns None if can't."""
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
        if "ground ball" in desc:
            return cls.GROUNDOUT
        if "fly" in desc:
            return cls.FLYOUT
        if "line" in desc:
            return cls.LINEOUT
        return None