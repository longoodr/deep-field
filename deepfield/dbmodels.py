import os
from typing import Optional

from peewee import (CharField, DateField, FixedCharField, ForeignKeyField,
                    IntegerField, Model, SmallIntegerField, SqliteDatabase,
                    TimeField)

_DB_NAME: Optional[str] = None
_PROD_DB_NAME = "stats.db"
_TEST_DB_NAME = "tmp.db"

db = SqliteDatabase(None)

class DeepFieldModel(Model):
    class Meta:
        database = db

class Venue(DeepFieldModel):
    name = CharField(unique=True)
    
class Team(DeepFieldModel):
    name = CharField(unique=True)
    abbreviation = FixedCharField(3)
    
class Player(DeepFieldModel):
    name = CharField()
    name_id = CharField(9, unique=True)
    bats = SmallIntegerField()
    throws = SmallIntegerField()

class Game(DeepFieldModel):
    name_id = FixedCharField(12, unique=True)
    local_start_time = TimeField("%H:%M", null=True)
    time_of_day = SmallIntegerField(null=True)
    field_type = SmallIntegerField(null=True)
    date = DateField()
    venue_id = ForeignKeyField(Venue, null=True)
    home_team_id = ForeignKeyField(Team)
    away_team_id = ForeignKeyField(Team)
    
class Play(DeepFieldModel):
    game_id = ForeignKeyField(Game)
    inning_half = SmallIntegerField()
    start_outs = SmallIntegerField()
    start_on_base = SmallIntegerField()
    play_num = SmallIntegerField()
    desc = CharField()
    pitch_ct = CharField(null=True)
    batter_id = ForeignKeyField(Player)
    pitcher_id = ForeignKeyField(Player)

_MODELS = (Game, Play, Player, Team, Venue)

def create_tables() -> None:
    db.create_tables(_MODELS)
    
def drop_tables() -> None:
    db.drop_tables(_MODELS)

def init_db() -> None:
    global _DB_NAME
    _DB_NAME = _TEST_DB_NAME if "TESTING" in os.environ else _PROD_DB_NAME
    db.init(_DB_NAME)
    create_tables()

def get_db_name() -> str:
    global _DB_NAME
    if _DB_NAME is None:
        raise RuntimeError("Database not initialized")
    return _DB_NAME

def get_data_name() -> str:
    if "TESTING" in os.environ:
        return "test_data"
    return "data"
