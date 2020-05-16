from os import environ
from pathlib import Path

from deepfield.data.bbref_pages import BBRefLink, GamePage
from deepfield.data.dbmodels import create_tables, db, drop_tables
from deepfield.data.enums import Handedness
from deepfield.data.pages import HtmlCache

db.init(":memory:")
environ["TESTING"] = "TRUE"

resources = HtmlCache.get()

def clean_db():
    drop_tables()
    create_tables()
