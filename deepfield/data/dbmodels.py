from peewee import (CharField, DateField, FixedCharField, ForeignKeyField,
                    SmallIntegerField, SqliteDatabase, TimeField)


class DeepFieldDatabase:
    _instance = None
    
    def __new__(cls, path='stats.db'):
        if cls._instance is None:
            cls._instance = super(DeepFieldDatabase, cls).__new__(cls)
            cls.__init_instance(path)
        return cls._instance

    @classmethod
    def __init_instance(cls, path):
        cls._instance.db = SqliteDatabase(path)
        cls._instance.db.create_tables([Game, Venue, Team, Player, Play])

class DeepFieldModel(Model):
    class Meta:
        database = DeepFieldDatabase().db

class Game(DeepFieldModel):
    name = CharField()
    local_start_time = TimeField("%H:%M")
    time_of_day = SmallIntegerField()
    field_type = SmallIntegerField()
    date = DateField()
    venue_id = ForeignKeyField(Venue)
    home_team_id = ForeignKeyField(Team)
    away_team_id = ForeignKeyField(Team)
    
class Venue(DeepFieldModel):
    name = CharField()
    
class Team(DeepFieldModel):
    name = CharField()
    abbreviation = FixedCharField(3)
    
class Player(DeepFieldModel):
    name = CharField()
    bats = SmallIntegerField()
    throws = SmallIntegerField()
    
class Play(DeepFieldModel):
    game_id = ForeignKeyField(Game)
    inning_num = SmallIntegerField()
    inning_half = SmallIntegerField()
    start_outs = SmallIntegerField()
    start_on_base = SmallIntegerField()
    play_num = SmallIntegerField()
    play_desc = CharField()
    batter_id = ForeignKeyField(Player)
    pitcher_id = ForeignKeyField(Player)
