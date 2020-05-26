from typing import Dict, Iterable, Tuple

from deepfield.dbmodels import Play, PlayNode

Node = Tuple[int, int, int]

class LevelOrderTraversal:
    """Iterates over the maximal antichains of the saved play graph."""

    _FIELDS = (PlayNode.play_id, PlayNode.outcome, Play.batter_id, Play.pitcher_id)

    def __iter__(self):
        self._cur_level = 0
        return self

    def __next__(self) -> Iterable[Dict[str, int]]:
        """Returns a generator which contains the dicts of the batter_id, 
        pitcher_id, play_id, and outcome of each node in the next level.
        """
        query = (PlayNode.select(*self._FIELDS)
                .join(Play)
                .where(PlayNode.level == self._cur_level)
                .dicts()
            )
        if query.count() == 0:
            raise StopIteration
        self._cur_level += 1
        return query.iterator()
