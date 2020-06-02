# Deep Field

### Scraping
`deepfield/scraping/scraper.py` is a script that will scrape games from www.baseball-reference.com into a database named `stats.db`.

**Note: this scraper can take a long time to run!** www.baseball-reference.com/robots.txt specifies a crawl delay of 3 seconds, and depending on how many years you decide to scrape, this can take anywhere from a few hours to a few days, since there are thousands of pages that need to scraped for a given season.

However, the scraper will cache the pages, so if you delete the database, subsequent scrapes will use the cached pages instead of requesting it via the web. This can make subsequent scrapes faster by an order of magnitude.
___
### Model input data generation
`deepfield/input/generator.py` is a script that will convert the plays in `stats.db` into a dataset for model training.

Each data point corresponds to a play in the database; the goal is to predict the outcome for each play. They contain a few distinct pieces of information that are relevant for outcome prediction:
* For the batter involved in the matchup, an estimate of their outcome distribution in the short term (100 plays), mid term (1000 plays), and long term (10000 plays), split by opposing pitcher handedness (see below for how these esimates are computed).
* Similar estimations for the pitcher involved in the matchup.
* Similar estimations for average batter performance. However, each timescale uses 10x the number of plays for individual players, to give a more accurate view of how the league as a whole is performing over each timescale. To give a sense of scale, there are a little over 200000 plays in a given season, so the long term estimation roughly captures performance over the last half-season.
* Similar estimations for average pitcher performance.
* Total number of appearances for this batter. This is intended to estimate the accuracy of the estimated distribution for the batter.
* Total number of appearances for this pitcher, for similar reasons.
* Total number of appearances for this pitcher in the game. This is intended to estimate pitcher fatigue.

Each rating is initialized to an estimate of the average outcome distribution over all plays in the database. The script iterates over all plays in order of occurrence; upon each seen matchup, the ratings are updated as follows:
* The outcome's corresponding one-hot vector *v* is generated. This can be considered the "actual" outcome distribution for this matchup, as opposed to the "expected" distribution of the players' ratings.
* For each event *e*, with corresponding entry *v<sub>e</sub>* in *v*, and current estimated probability *p<sub>e</sub>(t)* in the rating which is averaged over the last *k* plays,

<p align="center">
    <img src="https://latex.codecogs.com/svg.latex?p_e(t%2B1)%3D\left\{\begin{array}{ll}1-e^{\ln(1-p_e(t))-\frac{1}{k}}%20%26\quad%20v_e%3D1%20\\e^{\ln(p_e(t))-\frac{1}{k}}%26\quad%20v_e%3D0\end{array}\right." />
</p>

* This is a form of exponential smoothing, which increases the observed outcome's probability and decreases all other probabilities according to an exponential curve.

___