from abc import ABC, abstractmethod
from math import exp, log
from typing import Dict, Iterable

import numpy as np

from deepfield.enums import Outcome


class PlayerRatings:
    """A set of ratings for players that can be updated as plays are 
    evaluated.
    """

    def __init__(self):
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

    def update(self, event: np.ndarray, bid: int, pid: int)\
            -> None:
        """Updates the ratings for the given players."""
        self.get_batter(bid).update(event)
        self.get_pitcher(pid).update(event)
        self._avg_batter.update(event)
        self._avg_pitcher.update(event)

    def get_matchup_ratings(self, nodes: Iterable[Dict[str, int]]) -> np.ndarray:
        """Returns the matchup ratings for the given nodes."""
        diffs = [self.get_matchup_rating(n["batter_id"], n["pitcher_id"])
                 for n in nodes]
        return np.stack(diffs)

    def get_matchup_rating(self, bid: int, pid: int) -> np.ndarray:
        """Returns the matchup rating for the given players."""
        brating = self.get_batter(bid)
        prating = self.get_pitcher(pid)
        b_vs_avg = brating.get_rating() - self._avg_batter.get_rating()
        p_vs_avg = prating.get_rating() - self._avg_pitcher.get_rating()
        return np.concatenate(
                [
                    b_vs_avg,
                    p_vs_avg,
                    brating.appearances,
                    prating.appearances,
                ],
                axis=None
            )

class AbstractPlayerRating:
    """Tracks rating data for matchups."""

    def __init__(self, subratings: Iterable["AbstractSubrating"]):
        self._subratings = list(subratings)

    def reset(self) -> None:
        """Resets the rating to its initial value."""
        for subrating in self._subratings:
            subrating.reset()

    def update(self, event: np.ndarray) -> None:
        """Updates the ratings with the given event. This should be a one-hot
        vector.
        """
        for subrating in self._subratings:
            subrating.update(event)

    def get_rating(self) -> np.ndarray:
        """Returns the value of this rating."""
        return np.concatenate([s.rating for s in self._subratings], axis=None)

class AvgPlayerRating(AbstractPlayerRating):
    """Represents the rating of the average player at a given point in time,
    over several timescales.
    """

    def __init__(self):
        self.short_term = AvgPlayerSubrating(1000)
        self.mid_term = AvgPlayerSubrating(10000)
        self.long_term = AvgPlayerSubrating(100000)
        subratings = [self.short_term, self.mid_term, self.long_term]
        super().__init__(subratings)

class PlayerRating(AbstractPlayerRating):
    """A set of rating data for a given player over several timescales."""

    def __init__(self, avg_rating: AvgPlayerRating):
        self.short_term = PlayerSubrating(100, avg_rating.short_term)
        self.mid_term = PlayerSubrating(1000, avg_rating.mid_term)
        self.long_term = PlayerSubrating(10000, avg_rating.long_term)
        subratings = [self.short_term, self.mid_term, self.long_term]
        super().__init__(subratings)
        self.appearances = 0

    def update(self, event: np.ndarray) -> None:
        super().update(event)
        self.appearances += 1

class AbstractSubrating(ABC):
    """A moving average of performance over a given number of plays."""

    def __init__(self, plays_over: int):
        self.rating = self._initial_value()
        self._weight = 1 / plays_over

    def update(self, event: np.ndarray) -> None:
        update_funcs = [
                self._pos_update if event[i] >= self.rating[i]
                else self._neg_update
                for i in range(event.size)
            ]
        self.rating = np.asarray([
                update(x) for update, x in zip(update_funcs, self.rating)
            ])

    # see https://www.desmos.com/calculator/lffptb95tq for a visual explanation
    # of these updates
    def _pos_update(self, x):
        return 1 - exp(log(1-x) - self._weight)

    def _neg_update(self, x):
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
