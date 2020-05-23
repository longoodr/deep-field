from enum import Enum, IntFlag

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
    def from_desc(cls, desc: str) -> "Outcome":
        # TODO
        return cls.STRIKEOUT