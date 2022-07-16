from abc import ABC, abstractmethod
from math import exp, log
from typing import Dict, Iterable, Tuple

import numpy as np
from keras.utils import to_categorical

from deepfield.dbmodels import Player
from deepfield.enums import Handedness, Outcome


class PlayerRatings:
    """A set of ratings for players that can be updated as plays are 
    evaluated.
    """

    def __init__(self):
        self.hands = HandednessTracker()
        self.reset()

    def get_batter(self, bid: int) -> "PlayerRating":
        if bid not in self._bratings:
            self._bratings[bid] = PlayerRating(self._avg_batter)
        return self._bratings[bid]

    def get_pitcher(self, pid: int) -> "PlayerRating":
        if pid not in self._pratings:
            self._pratings[pid] = PlayerRating(self._avg_pitcher)
        return self._pratings[pid]

    def reset(self):
        """Resets all player ratings."""
        self._bratings: Dict[int, "PlayerRating"] = {}
        self._pratings: Dict[int, "PlayerRating"] = {}
        self._avg_batter = AvgPlayerRating()
        self._avg_pitcher = AvgPlayerRating()

    def update(self, bid: int, pid: int, event: np.ndarray)\
            -> None:
        """Updates the ratings for the given players."""
        bat_against_hand, pit_against_hand = \
                self.hands.get_bat_pit_against_handednesses(bid, pid)
        self.get_batter(bid).update(event, bat_against_hand)
        self.get_pitcher(pid).update(event, pit_against_hand)
        self._avg_batter.update(event, bat_against_hand)
        self._avg_pitcher.update(event, pit_against_hand)

    def get_matchup_rating(self,
                           bid: int,
                           pid: int,
                           pit_appearances: int = 0
                           ) -> np.ndarray:
        """Returns the matchup rating for the given players. `pit_appearances`
        specifies the number of appearances the pitcher has accumulated for the
        current game.
        """
        brating = self.get_batter(bid)
        prating = self.get_pitcher(pid)
        b_avg = self._avg_batter.get_rating()
        p_avg = self._avg_pitcher.get_rating()
        b_hand = to_categorical(
                self.hands.get_batter_handedness(bid), len(Handedness))
        p_hand = to_categorical(
                self.hands.get_pitcher_handedness(pid), len(Handedness))
        return np.concatenate(
                [
                    brating.get_rating(),
                    prating.get_rating(),
                    b_avg,
                    p_avg,
                    b_hand,
                    p_hand,
                    brating.appearances,
                    prating.appearances,
                    pit_appearances
                ],
                axis=None
            )

class HandednessTracker:
    """Returns handedness info for requested players."""

    _LEFT = Handedness.LEFT.value
    _RGHT = Handedness.RIGHT.value
    _BOTH = Handedness.BOTH.value
        
    _CHOOSE_OPPOSITE = {
            _LEFT: _RGHT,
            _RGHT: _LEFT
        }

    def __init__(self):
        self._pit_hand: Dict[int, int] = {}
        self._bat_hand: Dict[int, int] = {}

    def get_pitcher_handedness(self, pid: int) -> int:
        if pid not in self._pit_hand:
            hand = Player.get(Player.id == pid).throws
            self._pit_hand[pid] = hand
        return self._pit_hand[pid]

    def get_batter_handedness(self, bid: int) -> int:
        if bid not in self._bat_hand:
            hand = Player.get(Player.id == bid).bats
            self._bat_hand[bid] = hand
        return self._bat_hand[bid]

    def get_bat_pit_against_handednesses(self, bid: int, pid: int)\
            -> Tuple[int, int]:
        """Returns a tuple of the handednesses that the batter and pitcher are
        facing for the given matchup, respectively.
        """
        b_hand = self.get_batter_handedness(bid)
        p_hand = self.get_pitcher_handedness(pid)
        if b_hand != self._BOTH and p_hand != self._BOTH:
            return p_hand, b_hand
        # based on https://tinyurl.com/y89epnls, assume switch pitcher vs
        # switch hitter implies pitcher pitches left and batter bats right. 
        # (This almost never happens)
        if b_hand == self._BOTH and p_hand == self._BOTH:
            return (self._LEFT, self._RGHT)
        # switch batters prefer to bat opposite of pitcher
        if b_hand == self._BOTH:
            b_hand = self._CHOOSE_OPPOSITE[p_hand]
        # switch pitchers (i.e. Pat Venditte) prefer to pitch same as batter
        elif p_hand == self._BOTH:
            p_hand = b_hand
        return p_hand, b_hand

class AbstractPlayerRating:
    """Tracks rating data for matchups."""

    def __init__(self,
                 against_left: Iterable["AbstractSubrating"],
                 against_right: Iterable["AbstractSubrating"],
                 against_everyone: Iterable["AbstractSubrating"],
                 ):
        against_left = list(against_left)
        against_right = list(against_right)
        self._against_everyone = list(against_everyone)
        self._against_hand_subratings = {
                Handedness.LEFT.value: against_left,
                Handedness.RIGHT.value: against_right
            }
        self._subratings = against_left + against_right + self._against_everyone

    def reset(self) -> None:
        """Resets the rating to its initial value."""
        for subrating in self._subratings:
            subrating.reset()

    def update(self, event: np.ndarray, against_hand: int) -> None:
        """Updates the ratings with the given event. This should be a one-hot
        vector.
        """
        for subrating in self._against_hand_subratings[against_hand]:
            subrating.update(event)
        for subrating in self._against_everyone:
            subrating.update(event)

    def get_rating(self) -> np.ndarray:
        """Returns the value of this rating."""
        return np.concatenate([s.rating for s in self._subratings], axis=None)

class AvgPlayerRating(AbstractPlayerRating):
    """Represents the rating of the average player at a given point in time,
    over several timescales.
    """

    SHORT = 1000
    MID = 10000
    LONG = 100000

    def __init__(self):
        self.short_against_left = AvgPlayerSubrating(self.SHORT)
        self.mid_against_left = AvgPlayerSubrating(self.MID)
        self.long_against_left = AvgPlayerSubrating(self.LONG)
        against_left = [
                self.short_against_left,
                self.mid_against_left,
                self.long_against_left
            ]
        self.short_against_right = AvgPlayerSubrating(self.SHORT)
        self.mid_against_right = AvgPlayerSubrating(self.MID)
        self.long_against_right = AvgPlayerSubrating(self.LONG)
        against_right = [
                self.short_against_right,
                self.mid_against_right,
                self.long_against_right
            ]
        self.short_against_everyone = AvgPlayerSubrating(self.SHORT)
        self.mid_against_everyone = AvgPlayerSubrating(self.MID)
        self.long_against_everyone = AvgPlayerSubrating(self.LONG)
        against_everyone = [
            self.short_against_everyone,
            self.mid_against_everyone,
            self.long_against_everyone
        ]
        super().__init__(against_left, against_right, against_everyone)

class PlayerRating(AbstractPlayerRating):
    """A set of rating data for a given player over several timescales."""

    SHORT = 100
    MID = 1000
    LONG = 10000

    def __init__(self, avg_rating: AvgPlayerRating):
        self.short_against_left = PlayerSubrating(self.SHORT, avg_rating.short_against_left)
        self.mid_against_left = PlayerSubrating(self.MID, avg_rating.mid_against_left)
        self.long_against_left = PlayerSubrating(self.LONG, avg_rating.long_against_left)
        against_left = [
                self.short_against_left,
                self.mid_against_left,
                self.long_against_left
            ]
        self.short_against_right = PlayerSubrating(self.SHORT, avg_rating.short_against_right)
        self.mid_against_right = PlayerSubrating(self.MID, avg_rating.mid_against_right)
        self.long_against_right = PlayerSubrating(self.LONG, avg_rating.long_against_right)
        against_right = [
                self.short_against_right,
                self.mid_against_right,
                self.long_against_right
            ]
        self.short_against_everyone = PlayerSubrating(self.SHORT, avg_rating.short_against_everyone)
        self.mid_against_everyone = PlayerSubrating(self.MID, avg_rating.mid_against_everyone)
        self.long_against_everyone = PlayerSubrating(self.LONG, avg_rating.long_against_everyone)
        against_everyone = [
            self.short_against_everyone,
            self.mid_against_everyone,
            self.long_against_everyone
        ]
        super().__init__(against_left, against_right, against_everyone)
        self.appearances = 0

    def update(self, event: np.ndarray, against_hand: int) -> None:
        super().update(event, against_hand)
        self.appearances += 1

class AbstractSubrating(ABC):
    """A moving average of performance over a given number of plays."""

    def __init__(self, plays_over: int):
        self.rating = self._initial_value()
        self._weight = 1 / plays_over

    def update(self, event: np.ndarray) -> None:
        update_funcs = [
                self._pos_update if event[i] == 1
                else self._neg_update
                for i in range(event.size)
            ]
        self.rating = np.asarray([
                update(x) for update, x in zip(update_funcs, self.rating)
            ])

    # see https://www.desmos.com/calculator/eqilnfnshh for a visual explanation
    # of these updates
    def _pos_update(self, x):
        if x == 1:
            return 1
        return 1 - exp(log(1-x) - self._weight)

    def _neg_update(self, x):
        if x == 0:
            return 0
        return exp(log(x) - self._weight)

    def reset(self) -> None:
        """Resets this rating to its initial value."""
        self.rating = self._initial_value()

    @abstractmethod
    def _initial_value(self) -> np.ndarray:
        """Returns the initial value of this rating."""
        pass

class AvgPlayerSubrating(AbstractSubrating):
    """The average player's initial value is the percentage array for outcomes
    over all plays in the database.
    """

    _init_val: np.ndarray = None

    def __init__(self, plays_over: int):
        self._ensure_init_val_set()
        super().__init__(plays_over)

    @classmethod
    def _ensure_init_val_set(cls):
        if cls._init_val is None:
            cls._init_val =  Outcome.get_percentages()

    def _initial_value(self) -> np.ndarray:
        return self._init_val

class PlayerSubrating(AbstractSubrating):
    """A player's initial value is whatever the current average player rating
    is.
    """

    def __init__(self, plays_over: int, avg_subrating: AvgPlayerSubrating):
        self._avg = avg_subrating
        super().__init__(plays_over)

    def _initial_value(self):
        return self._avg.rating
