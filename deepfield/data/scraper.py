import argparse
import logging
import sys
from datetime import datetime
from typing import Iterable

from requests.exceptions import HTTPError

from deepfield.data.bbref_pages import BBRefLink, SchedulePage
from deepfield.data.nodes import ScrapeNode
from deepfield.data.pages import Page
from deepfield.data.dbmodels import db, create_tables

logger = logging.getLogger()
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)

CUR_YEAR = datetime.now().year

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description = "Scrapes data from baseball-reference.com.")
    parser.add_argument("year", type=check_year, 
                        help="year to scrape"
        )
    parser.add_argument("-n", "--no-earlier",
                        action = "store_true",
                        help = "will scrape everything for given year and afterward (default: scrape only given year)"
        )
    return parser.parse_args()

def main(args: argparse.Namespace) -> None:
    db.init("stats.db")
    create_tables()
    for y in get_years(args.year, args.no_earlier):
        try:
            scrape_year(y)
        except HTTPError as e:
            logger.warning(f"Got code {e.response.status_code} when trying to scrape year {y}. Skipping")
    
def scrape_year(year: int) -> None:
    sched_url = f"https://www.baseball-reference.com/leagues/MLB/{year}-schedule.shtml"
    sched_link = BBRefLink(sched_url)
    # since the current year's schedule will be continually updated as new games
    # are played, do not want to use cached version of its page
    use_cache = False if year == CUR_YEAR else True
    sched = Page.from_link(sched_link, use_cache)
    ScrapeNode(sched).scrape()

def check_year(string: str) -> int:
    year = int(string)
    if year > CUR_YEAR:
        raise argparse.ArgumentTypeError(f"Choose a year no later than {CUR_YEAR}")
    return year

def get_years(year: int, no_earlier: bool) -> Iterable[int]:
    if no_earlier:
        for y in range(CUR_YEAR, year - 1, -1):
            yield y
    else:
        yield year

if __name__ == "__main__":
    args = parse_args()
    main(args)
