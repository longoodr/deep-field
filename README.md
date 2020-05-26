# Deep Field

### Scraping
`deepfield/scraping/scraper.py` is a script that will scrape games from www.baseball-reference.com into a database named `stats.db`.

**Note: this scraper can take a long time to run!** www.baseball-reference.com/robots.txt specifies a crawl delay of 3 seconds, and depending on how many years you decide to scrape, this can take anywhere from a few hours to a few days, since there are thousands of pages that need to scraped for a given season.

However, the scraper will cache the pages, so if you delete the database, subsequent scrapes will use the cached pages instead of requesting it via the web. This can make subsequent scrapes faster by an order of magnitude.
___
### Play Dependency Graph Construction
`deepfield/playgraph/playgraph_builder.py` is a script that will build a play dependency graph from the plays in `stats.db` and save the graph's nodes and edges to `stats.db`.

The play dependency graph is a [directed acyclic graph](https://en.wikipedia.org/wiki/Directed_acyclic_graph). This directed acyclic graph can also be represented a [partially ordered set (poset)](https://en.wikipedia.org/wiki/Partially_ordered_set). Then, the [maximal antichains](https://en.wikipedia.org/wiki/Antichain#Height_and_width) of this poset represent sets of plays which can evaluated independently of one another, without requiring any rating updates for the involved players. 

Note that these maximal antichains must still be evaluated in the proper sequence for player ratings to be up-to-date within each maximal antichain, with respect to all previous plays. Therefore, during model evaluation, the [lattice](https://en.wikipedia.org/wiki/Lattice_(order)) of maximal antichains of the poset is traversed, with each maximal antichain being evaluated as a unit. After each maximal antichain is evaluated, ratings are updated. This ensures that:

1. For any two plays involving the same player, the earlier of the two plays is evaluated in an earlier maximal antichain relative to the later play. Therefore, for a given play, the ratings of the players are up-to-date with respect to all previous plays involving those players.

2. Play counts are relatively evenly distributed across players for a given number of evaluated plays. With the most basic play evaluation order where plays are merely evaluated sequentially by time of occurrence, this would not be the case.

3. Plays within a maximal antichain to be used as a training batch for the outcome prediction model, since the ratings can be held constant.
___