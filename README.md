# Deep Field
Deep Field is an attempt to answer the question: "given an arbitrary batter and pitcher matchup in Major League Baseball, is it possible to predict the probabilities of what will happen when they face each other at the plate?"

To help answer this, a web scraper is used to pull play-by-play information from [baseball-reference.com](https://www.baseball-reference.com/).

### Setup
This project requires [Python](https://www.python.org/downloads/) to be installed.
1. Clone the repo.
2. From the root directory, in a terminal run
```
python -m venv .venv
.venv/Scripts/activate
python -m pip install -r requirements.txt
```

You will need to run `.venv/Scripts/activate` for each new terminal.

### Scraping
The web scraper can be invoked by running 
```
`python -m deepfield.scraper start-year [end-year-inclusive]
```
from the root. This scraper builds up a SQLite database of play-by-play information for every game in the given year range.

**Note: this scraper can take a long time to run!** [baseball-reference.com/robots.txt](https://www.baseball-reference.com/robots.txt) specifies a crawl delay of 3 seconds, and depending on how many years you decide to scrape, this can take anywhere from a few hours to a few days, since there are thousands of pages that need to scraped for a given season.

However, the scraper will cache the pages, so if you delete the database, subsequent scrapes will use the cached pages instead of requesting it via the web. This can make subsequent scrapes faster by an order of magnitude.