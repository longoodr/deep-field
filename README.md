# Deep Field

### Scraping
`deepfield/scraping/scraper.py` is a script that will scrape games from www.baseball-reference.com into a database named `stats.db`.

**Note: this scraper can take a long time to run!** www.baseball-reference.com/robots.txt specifies a crawl delay of 3 seconds, and depending on how many years you decide to scrape, this can take anywhere from a few hours to a few days, since there are thousands of pages that need to scraped for a given season.

However, the scraper will cache the pages, so if you delete the database, subsequent scrapes will use the cached pages instead of requesting it via the web. This can make subsequent scrapes faster by an order of magnitude.

### Play Dependency Graph Construction
`deepfield/playgraph/playgraph_builder.py` is a script that will build a play dependency graph from the plays in `stats.db` and save the graph's nodes and edges to `stats.db`.

The play dependency graph is a [directed acyclic graph](https://en.wikipedia.org/wiki/Directed_acyclic_graph). For model evaluation, a [topological sort](https://en.wikipedia.org/wiki/Topological_sorting) of this play dependency graph is used to evaluate plays in an order that ensures:
1. For any two plays involving the same player, the earlier of the two plays is evaluated before the later one. This ensures for a given play, the ratings of the players are consistent with all previous plays involving those players.
2. Play counts are evenly distributed across players for a given number of evaluated plays. This would not be the case if the plays were evaluated sequentially by time of occurrence.