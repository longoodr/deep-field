import argparse
import time
from datetime import datetime
from typing import Iterable

from deepfield.db.models import init_db
from deepfield.scraping import BBREF_CRAWL_DELAY
from deepfield.scraping.bbref_pages import BBRefLink
from deepfield.scraping.nodes import ScrapeNode
from deepfield.scraping.pages import Page
from deepfield.script_utils import config_logging, logger

EARLIEST_YEAR = 1871
CUR_YEAR = datetime.now().year

# TODO Add db name, crawl delay as parameter.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrapes data from baseball-reference.com.")
    parser.add_argument("start_year", type=parse_year,
                        help="Starting year to scrape.")
    parser.add_argument("end_year", type=parse_year, default=CUR_YEAR,
                         help="Ending year to scrape, inclusive. If not specified, defaults to current year.")
    parser.add_argument("-c", "--crawl-delay", type=parse_crawl_delay, default=BBREF_CRAWL_DELAY,
                        help="The crawl delay to use, in seconds. baseball-reference.com/robots.txt specifies a " +
                        f"crawl delay of {BBREF_CRAWL_DELAY} seconds, which is the default.")
    parser.add_argument("-db", "--database-name", type=)
    return parser.parse_args()

def main(args: argparse.Namespace) -> None:
    if (args.start_year > args.end_year):
        raise argparse.ArgumentError(f"Starting year cannot be greater than ending year")
    init_db()
    try:
        for y in range(args.start_year, args.end_year + 1):
            scrape_year(y, args.crawl_delay)
    except KeyboardInterrupt:
        logger.info("Ending scrape")

def scrape_year(year: int, crawl_delay: float) -> None:
    sched_url = f"https://www.baseball-reference.com/leagues/MLB/{year}-schedule.shtml"
    sched_link = BBRefLink(sched_url)
    # since the current year's schedule will be continually updated as new games
    # are played, do not want to use cached version of its page
    use_cache = False if year == CUR_YEAR else True
    sched = Page.from_link(sched_link, use_cache)
    ScrapeNode.from_page(sched).scrape(crawl_delay)

def parse_year(string: str) -> int:
    year = int(string)
    if year < EARLIEST_YEAR:
        raise ValueError(f"Choose a year no earlier than {EARLIEST_YEAR}")
    if year > CUR_YEAR:
        raise ValueError(f"Choose a year no later than {CUR_YEAR}")
    return year

def parse_crawl_delay(string: str) -> float:
    delay = float(string)
    if delay < 0:
        raise ValueError("Crawl delay cannot be negative")
    if delay < BBREF_CRAWL_DELAY:
        logger.warning(f"baseball-reference.com specifies a crawl delay of {BBREF_CRAWL_DELAY} seconds," +
            "but you gave {delay}. It's highly recommended to be polite and abide by their crawl delay." +
            "Scrape at your own risk!")
        time.sleep(3)
    return delay

def get_years(year: int, no_earlier: bool) -> Iterable[int]:
    if no_earlier:
        for y in range(CUR_YEAR, year - 1, -1):
            yield y
    else:
        yield year

if __name__ == "__main__":
    config_logging()
    args = parse_args()
    main(args)
