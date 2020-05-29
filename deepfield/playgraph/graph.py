from typing import Dict, Iterable, List, Tuple

from deepfield.dbmodels import Play, PlayNode

Node = Tuple[int, int, int]

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
        if self._done:
            raise StopIteration
        self._done = True
        return level
        
