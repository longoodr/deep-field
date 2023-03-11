from enum import Enum, IntFlag

class OnBase(IntFlag):
    EMPTY = 0
    FIRST = 1
    SECOND = 2
    THIRD = 4

class TimeOfDay(Enum):
    DAY = 0
    NIGHT = 1

class FieldType(Enum):
    TURF = 0
    GRASS = 1

class InningHalf(Enum):
    TOP = 0
    BTM = 1

class Handedness(Enum):
    LEFT = 0
    RIGHT = 1
    BOTH = 2
