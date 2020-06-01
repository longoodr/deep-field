import logging
from collections import Counter
from typing import Counter as CounterType
from typing import Dict, Iterable, List, Optional, Tuple

from deepfield.dbmodels import Game, Play, PlayNode
from deepfield.enums import Outcome

Matchup = Tuple[int, int, int]

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

        
class DbMatchupReader:
    """Reads plays from the database and produces the corresponding matchups
    that need to be evaluated to generate rating input data.
    """

    LOG_FRAC_INTERVAL = 0.01

    def __iter__(self):
        query = self.__get_plays()
        self._plays = query.iterator()
        self._ct = query.count()
        self._num = 0
        self._num_none = 0
        self._next_frac = self.LOG_FRAC_INTERVAL
        return self

    def __next__(self) -> Matchup:
        node = None
        while node is None:
            play = next(self._plays)
            node = self._get_matchup_from_play(play)
        self._num += 1
        self._log_progress()
        return node

    def _log_progress(self):
        if self._num % 1000 != 0:
            return
        frac_none = self._num_none / self._num
        frac_not_none = 1 - frac_none
        est_ct = int(self._ct * frac_not_none)
        frac_processed = self._num / est_ct
        if frac_processed >= self._next_frac:
            logger.info(f"{self._num} of estimated total {est_ct} matchups read")
            self._next_frac += self.LOG_FRAC_INTERVAL

    def _get_matchup_from_play(self, play) -> Optional[Matchup]:
        outcome = Outcome.from_desc(play.desc)
        if outcome is None:
            self._num_none += 1
            return None
        return (play.batter_id, play.pitcher_id, outcome.value)

    @staticmethod
    def __get_plays():
        return (Play
                .select(Play.id, Play.batter_id, Play.pitcher_id, Play.desc)
                .join(Game, on=(Play.game_id == Game.id))
                .order_by(Game.date, Play.game_id, Play.play_num)
                .namedtuples()
            )
