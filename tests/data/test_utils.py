from pathlib import Path

def get_res_path(name: str) -> Path:
    base_path = Path(__file__).parent
    return (base_path / ("resources/" + name)).resolve()