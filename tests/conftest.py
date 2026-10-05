import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "data" / "cinerocket.db"
needs_db = pytest.mark.skipif(not DB_PATH.exists(), reason="data/cinerocket.db não encontrado")


@pytest.fixture(scope="session")
def conn():
    from cinedata_agent.db import connect_readonly

    return connect_readonly(DB_PATH)
