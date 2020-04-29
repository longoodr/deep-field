from enum import Enum, Flag

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

class OnBase(Flag):
    FIRST = 1
    SECOND = 2
    THIRD = 4