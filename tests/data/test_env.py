from os import environ
from pathlib import Path

from deepfield.data.bbref_pages import BBRefLink, GamePage
from deepfield.data.dbmodels import (Game, GamePlayer, Play, Player, Team,
                                     Venue, db)
from deepfield.data.pages import HtmlCache
from deepfield.data.enums import Handedness

_MODELS = (Game, GamePlayer, Play, Player, Team, Venue)

db.init(":memory:")
environ["TESTING"] = "TRUE"

resources = HtmlCache.get()

def clean_db():
    db.drop_tables(_MODELS)
    db.create_tables(_MODELS)