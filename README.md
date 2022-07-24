# Deep Field
Deep Field contains (among other things) a web scraper used to pull play-by-play information from [baseball-reference.com](https://www.baseball-reference.com/).

### Setup
1. Ensure the latest version of [Python](https://www.python.org/downloads/) is installed.
2. Clone the repo.
3. From the root, run `python -m pip install -r requirements.txt`

### Scraping
The web scraper can be invoked by running 
```
python -m deepfield.scraper start-year [end-year] [database-name]
```
from the root. This scraper builds up a SQLite database of play-by-play information for every game in the given year range.
* `start-year` is the earliest year to scrape.
* `end-year` is the latest year to scrape (inclusive). Defaults to current year.
* `database-name` is the name of the database to generate. Defaults to `stats`.

**Note: this scraper can take a long time to run!** [baseball-reference.com/robots.txt](https://www.baseball-reference.com/robots.txt) specifies a crawl delay of 3 seconds, and depending on how many years you decide to scrape, this can take anywhere from a few hours to a few days, since there are thousands of pages that need to scraped for a given season.

However, the scraper will cache the pages, so if you delete the database or reference a different name, subsequent scrapes will use the cached pages instead of requesting them via the web. This can make subsequent scrapes faster by an order of magnitude.