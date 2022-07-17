from reading import DbMatchupReader

class PlayDagGenerator:
    """Iterates over input plays and maintains a dependency DAG
    of plays, which can be queried to construct input data.
    """
    
    def __init__(self, reader: DbMatchupReader):
        self._reader = reader
        
    def __iter__(self):
        self._num = 0
        self._most_recent = None
        self._dag = 
        return iter(self._reader)
    
    def __next__(self):
        matchup = next(self._reader)
        # Build the DAG
        # Build mapping from (player, player_timestamp) -> DAG node
        # timestep increments for player per play