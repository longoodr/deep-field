# Deep Field

### Scraping
`deepfield/scraping/scraper.py` is a script that will scrape games from www.baseball-reference.com into a database named `stats.db`.

**Note: this scraper can take a long time to run!** www.baseball-reference.com/robots.txt specifies a crawl delay of 3 seconds, and depending on how many years you decide to scrape, this can take anywhere from a few hours to a few days, since there are thousands of pages that need to scraped for a given season.

However, the scraper will cache the pages, so if you delete the database, subsequent scrapes will use the cached pages instead of requesting it via the web. This can make subsequent scrapes faster by an order of magnitude.
___
### Model input data generation

WIP
___