import argparse
from datetime import datetime
from typing import Iterable

from deepfield.dbmodels import init_db
from deepfield.scraping.bbref_pages import BBRefLink
from deepfield.scraping.nodes import ScrapeNode
from deepfield.scraping.pages import Page
from deepfield.script_utils import config_logging, logger

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
    config_logging()
    init_db()
    try:
        for y in get_years(args.year, args.no_earlier):
            scrape_year(y)
    except KeyboardInterrupt:
        logger.info("Ending scrape")
    
def scrape_year(year: int) -> None:
    sched_url = f"https://www.baseball-reference.com/leagues/MLB/{year}-schedule.shtml"
    sched_link = BBRefLink(sched_url)
    # since the current year's schedule will be continually updated as new games
    # are played, do not want to use cached version of its page
    use_cache = False if year == CUR_YEAR else True
    sched = Page.from_link(sched_link, use_cache)
    ScrapeNode.from_page(sched).scrape()

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
