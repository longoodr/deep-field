# Deep Field
Deep Field is a web scraper used to pull play-by-play information from [baseball-reference.com](https://www.baseball-reference.com/). The web scraper scrapes the details of each play from every available game page and writes the information into an SQLite Database. It also scrapes some barebones info on players, games, teams, and venues. The full schema is described below.

Note this database is intended to be used to aggregate your own stats. It does not pull any aggregated stats or metrics itself.

### Setup
1. Ensure the latest version of [Python](https://www.python.org/downloads/) is installed.
2. Clone the repo.
3. From the root, run `python -m pip install -r requirements.txt`

### Scraping
The web scraper can be invoked by running 
```
python -m deepfield.scraper start-year [end-year] [-db database-name]
```
from the root.
This scraper builds up a SQLite database of play-by-play information for every game in the given year range. You can issue a keyboard interrupt via Ctrl+C to end the scrape.
* `start-year` is the earliest year to scrape.
* `end-year` is the latest year to scrape (inclusive). Defaults to current year.
* `database-name` is the name of the database to generate. Defaults to `stats`.

**Note: this scraper can take a long time to run!** [baseball-reference.com/robots.txt](https://www.baseball-reference.com/robots.txt) specifies a crawl delay of 3 seconds, and depending on how many years you decide to scrape, this can take anywhere from a few hours to a few days, since there are thousands of pages that need to scraped for a given season.

However, the scraper will cache the pages, so if you delete the database or reference a different name, subsequent scrapes will use the cached pages instead of requesting them via the web. This can make subsequent scrapes faster by an order of magnitude.

### Database details
The database contains the following tables. Each table section contains a description of each column.
- ### `play`
  Field | Description 
  ---|---
  `id`| An auto-incremented unique ID.
  `game_id`| The ID of the game the play belongs to.
  `inning_half`| A number corresponding to the half of the inning the play occurred in. This starts at 0 for the top of the 1st and goes to 17 for bottom of the 9th, continuing for overtime as needed.
  `start_outs`| Number of outs at the start of the play.
  `start_on_base`| A number in the range [0, 7] corresponding to which bases were occupied at the start of the play as a bit flag; i.e. +1 for first occupied, +2 for second occupied and +4 for third occupied.
  `play_num`| A 0-based index corresponding to the position that this play occurred in, relative to the game's other plays.
  `desc`| The listed description for the result of the play.
  `pitch_ct`| The listed information for the starting pitch count of the play. For modern games this contains the specifics of the pitches thrown as well. For earlier games, this may be minimal or omitted entirely.
  `batter_id`| ID of the batter who participated in the play.
  `pitcher_id`| ID of the pitcher who participated in the play.
- ### `player`
  Field | Description
  ---|---
  `id`| An auto-incremented unique ID.
  `name`| Name of the player.
  `name_id`| The name ID used by baseball-reference. This is typically the first five letters of the last name, first two letters of first name, and two unique digits.
  `bats`| 0 if this player bats left-handed, 1 if right-handed, and 2 if ambidextrous.
  `throws`| 0 if this player throws left-handed, 1 if right-handed, and 2 if ambidextrous.
- ### `game`
  Field | Description
  ---|---
  `id`| An auto-incremented unique ID.
  `name_id`| The name ID used by baseball-reference. This is typically the home team's three letter abbreviation, followed by the game date's year, month, and day, followed by a unique digit.
  `local_start_time`| The local start time of the game in the venue's timezone.
  `time_of_day`| 0 if the game was played during the day, 1 if at night.
  `field_type`| 0 if the game was played on turf, 1 if on grass.
  `date`| The date the game was played on.
  `venue_id`| ID of the venue the game was played in.
  `home_team_id`| ID of the home team.
  `away_team_id`| ID of the away team.
- ### `team`
  Field | Description
  ---|---
  `id`| An auto-incremented unique ID.
  `name`| Name of the team.
  `abbreviation`| Abbreviation for the team.
- ### `venue`
  Field | Description
  ---|---
  `id`| An auto-incremented unique ID.
  `name`| Name of the venue.
