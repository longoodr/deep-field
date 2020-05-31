import logging
from collections import Counter
from typing import Counter as CounterType
from typing import Dict, Iterable, List, Optional, Tuple

from deepfield.dbmodels import Game, Play, PlayNode
from deepfield.enums import Outcome

Node = Tuple[int, int, int]

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class LevelTraversal:
    """Iterates over the maximal antichains of the saved play graph."""

    _FIELDS = (PlayNode.play_id, PlayNode.outcome, Play.batter_id, Play.pitcher_id, PlayNode.level)

    def __iter__(self):
        self._cur_level = 0
        self._query = (PlayNode.select(*self._FIELDS)
                .join(Play)
                .order_by(PlayNode.level)
                .dicts()
                .iterator()
            )
        self._peek = None
        self._done = False
        return self

    def __next__(self) -> Iterable[Dict[str, int]]:
        """Returns a generator which contains the dicts of the batter_id, 
        pitcher_id, play_id, and outcome of each node in the next level.
        """
        level: List[Dict[str, int]] = []
        for row in self._query:
            if row["level"] > self._cur_level:
                if self._peek is not None:
                    level.append(self._peek)
                self._cur_level += 1
                self._peek = row
                return level
            level.append(row)
        if self._done or len(level) == 0:
            raise StopIteration
        self._done = True
        return level
        
class DbPlaysToGraphIterator():
    """Reads plays from the database and produces the corresponding nodes for
    the associated play graph.
    """

    LOG_FRAC_INTERVAL = 0.01

    def __iter__(self):
        query = self.__get_plays()
        self._plays = query.iterator()
        self._ct = query.count()
        # maps player id to level of their last play + 1 (i.e. 0 => no plays)
        # (+ 1, because node levels should be 0-indexed)
        self._player_to_lvl: CounterType[int] = Counter()
        self._num = 0
        self._num_none = 0
        self._next_frac = self.LOG_FRAC_INTERVAL
        return self

    def __next__(self) -> Node:
        node = None
        while node is None:
            play = next(self._plays)
            node = self._get_node_from_play(play)
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
            logger.info(f"{self._num} of estimated total {est_ct} nodes processed")
            self._next_frac += self.LOG_FRAC_INTERVAL

    def _get_node_from_play(self, play) -> Optional[Node]:
        outcome = Outcome.from_desc(play.desc)
        if outcome is None:
            self._num_none += 1
            return None
        level = self._get_node_level(play)
        self._player_to_lvl[play.batter_id] = level + 1
        self._player_to_lvl[play.pitcher_id] = level + 1
        return (play.id, outcome.value, level)

    def _get_node_level(self, play) -> int:
        bid = play.batter_id
        pid = play.pitcher_id
        b_lvl = self._player_to_lvl[bid]
        p_lvl = self._player_to_lvl[pid]
        return max(b_lvl, p_lvl)

    @staticmethod
    def __get_plays():
        return (Play
                .select(Play.id, Play.batter_id, Play.pitcher_id, Play.desc)
                .join(Game, on=(Play.game_id == Game.id))
                .order_by(Game.date, Play.game_id, Play.play_num)
                .namedtuples()
            )
