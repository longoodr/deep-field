import argparse
from datetime import datetime
from typing import Iterable


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
    for y in get_years(args.year, args.no_earlier):
        # TODO scrape the year
        pass

def check_year(string: str) -> int:
    year = int(string)
    c_year = cur_year()
    if year > c_year:
        raise argparse.ArgumentTypeError(f"Choose a year no later than {c_year}")
    return year

def get_years(year: int, no_earlier: bool) -> Iterable[int]:
    if no_earlier:
        for y in range(cur_year(), year - 1, -1):
            yield y
    else:
        yield year
        
def cur_year() -> int:
    return datetime.now().year

if __name__ == "__main__":
    args = parse_args()
    main(args)
