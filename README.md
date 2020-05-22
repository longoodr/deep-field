# Deep Field

### Scraping
`deepfield/data/scraper.py` is a script that will scrape games from www.baseball-reference.com into a database named `stats.db`.

Note this scraper may take a few days to run! www.baseball-reference.com/robots.txt specifies a crawl delay of 3 seconds, and depending on how many years you decide to scrape, this can take anywhere from a few hours to a few days. However, the scraper will cache the pages, so if you delete the database, subsequent scrapes will use the cached pages instead of requesting it via the web. This can make the process up to 20x faster.