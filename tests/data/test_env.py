from os import environ
from pathlib import Path

from deepfield.data.bbref_pages import BBRefLink, GamePage
from deepfield.data.dbmodels import (db, create_tables, drop_tables)
from deepfield.data.pages import HtmlCache
from deepfield.data.enums import Handedness

db.init(":memory:")
environ["TESTING"] = "TRUE"

resources = HtmlCache.get()

def clean_db():
    create_tables()
    drop_tables()