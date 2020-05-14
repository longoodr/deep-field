from os import environ
from pathlib import Path

from deepfield.data.bbref_pages import BBRefLink, GamePage
from deepfield.data.dbmodels import (Game, GamePlayer, Play, Player, Team,
                                     Venue, db)
from deepfield.data.scraper import HtmlCache
from deepfield.data.enums import Handedness

_MODELS = (Game, GamePlayer, Play, Player, Team, Venue)

db.init(":memory:")
environ["TESTING"] = "TRUE"

resources = HtmlCache.get()

def clean_db():
    db.drop_tables(_MODELS)
    db.create_tables(_MODELS)
    
def insert_mock_players(page: GamePage) -> None:
    ptables = page._player_tables
    with db.atomic():
        for table in ptables:
            pmap = table.get_name_to_name_ids()
            for name, name_id in pmap.items():
                _insert_mock_player(name, name_id)

def _insert_mock_player(name: str, name_id: str) -> None:
    fields = {
        "name": name,
        "name_id": name_id,
        "bats": Handedness.RIGHT.value,
        "throws": Handedness.RIGHT.value,
    }
    if Player.get_or_none(Player.name_id == name_id) is None:
        Player.create(**fields)