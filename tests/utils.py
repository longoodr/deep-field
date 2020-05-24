import os
from pathlib import Path

from deepfield.dbmodels import (Player, create_tables, db, drop_tables,
                                get_db_name, init_db)
from deepfield.enums import Handedness
from deepfield.scraping.bbref_pages import BBRefLink, GamePage
from deepfield.scraping.nodes import ScrapeNode
from deepfield.scraping.pages import HtmlCache, Page


def init_test_env() -> None:
    os.environ["TESTING"] = "True"
    init_db()
    clean_db()

def delete_db_file():
    db.close()
    os.remove(get_db_name())

def clean_db():
    drop_tables()
    create_tables()

def insert_game(url: str) -> None:
    link = BBRefLink(url)
    page = Page.from_link(link)
    insert_mock_players(page)  # type: ignore
    ScrapeNode.from_page(page).scrape()


def insert_mock_players(page: GamePage) -> None:
    ptables = page._player_tables
    with db.atomic():
        for table in ptables:
            for name, name_id in table.get_name_name_ids():
                _insert_mock_player(name, name_id)

def _insert_mock_player(name: str, name_id: str) -> None:
    fields = {
        "name": name,
        "name_id": name_id,
        "bats": Handedness.RIGHT.value,
        "throws": Handedness.RIGHT.value,
    }
    if Player.get_or_none(Player.name_id == name_id) is None:
        Player.create(**fields)
