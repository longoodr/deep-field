import argparse
import os
import time
from datetime import datetime

from pathvalidate.argparse import sanitize_filename_arg

from deepfield.db.models import init_db
from deepfield.scraping import BBREF_CRAWL_DELAY
from deepfield.scraping.bbref_pages import BBRefLink
from deepfield.scraping.nodes import ScrapeNode
from deepfield.scraping.pages import Page
from deepfield.script_utils import config_logging, logger

DEFAULT_DB_NAME = "stats"
EARLIEST_YEAR = 1920
CUR_YEAR = datetime.now().year

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrapes data from baseball-reference.com.")
    parser.add_argument("start_year", type=parse_year,
                        help="Starting year to scrape.")
    parser.add_argument("end_year", type=parse_year, default=CUR_YEAR, nargs='?',
                         help="Ending year to scrape, inclusive. If not specified, defaults to current year.")
    parser.add_argument("-db", "--database-name", type=parse_db_name, default=DEFAULT_DB_NAME)
    parser.add_argument("-c", "--crawl-delay", type=parse_crawl_delay, default=BBREF_CRAWL_DELAY,
                        help="The crawl delay to use, in seconds. baseball-reference.com/robots.txt specifies a " +
                        f"crawl delay of {BBREF_CRAWL_DELAY} seconds, which is the default.")
    return parser.parse_args()

def parse_db_name(arg: str) -> str:
    db = sanitize_filename_arg(arg)
    if len(arg) == 0:
        raise argparse.ArgumentTypeError("Database name cannot be empty")
    if arg[-1] == '.' or len(os.path.splitext(db)[1]) > 0:
        raise argparse.ArgumentTypeError("Database name should not include a file extension")
    return db

def parse_year(arg: str) -> int:
    year = int(arg)
    if year < EARLIEST_YEAR:
        raise argparse.ArgumentTypeError(f"Choose a year no earlier than {EARLIEST_YEAR}")
    if year > CUR_YEAR:
        raise argparse.ArgumentTypeError(f"Choose a year no later than {CUR_YEAR}")
    return year

def parse_crawl_delay(arg: str) -> float:
    delay = float(arg)
    if delay < 0:
        raise argparse.ArgumentTypeError("Crawl delay cannot be negative")
    warn_delay = 15
    if delay < BBREF_CRAWL_DELAY:
        logger.warning(f"baseball-reference.com specifies a crawl delay of {BBREF_CRAWL_DELAY} seconds, " +
            f"but you gave {delay}. It is HIGHLY RECOMMENDED to be polite and abide by their crawl delay. " +
            f"Starting scrape in {warn_delay} seconds.")
        time.sleep(15)
    return delay

def main(args: argparse.Namespace) -> None:
    if (args.start_year > args.end_year):
        raise argparse.ArgumentError(f"Starting year cannot be greater than ending year")
    init_db(args.database_name)
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
    use_cache = year != CUR_YEAR
    sched = Page.from_link(sched_link, use_cache)
    ScrapeNode.from_page(sched).scrape(crawl_delay)

if __name__ == "__main__":
    config_logging()
    args = parse_args()
    main(args)
