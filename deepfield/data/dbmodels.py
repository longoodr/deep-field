from peewee import (CharField, DateField, FixedCharField, ForeignKeyField,
                    Model, SmallIntegerField, SqliteDatabase, TimeField)

db = SqliteDatabase('stats.db')

class DeepFieldModel(Model):
    class Meta:
        database = db

class Venue(DeepFieldModel):
    name = CharField(unique=True)
    
class Team(DeepFieldModel):
    name = CharField(unique=True)
    abbreviation = FixedCharField(3, unique=True)
    
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
    venue_id = ForeignKeyField(Venue)
    home_team_id = ForeignKeyField(Team)
    away_team_id = ForeignKeyField(Team)
    
class GamePlayer(DeepFieldModel):
    game_id = ForeignKeyField(Game)
    player_id = ForeignKeyField(Player)
    
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

db.create_tables([Game, Venue, Team, Player, Play])