from pathlib import Path
from os import environ

environ["TESTING"] = "TRUE"

def get_res_path(name: str) -> Path:
    base_path = Path(__file__).parent
    return (base_path / ("resources/" + name)).resolve()