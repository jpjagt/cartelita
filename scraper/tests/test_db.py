from sqlalchemy import text
from cartelera.db import make_engine

TEST_URL = "postgresql://localhost:5432/cartelera_test"


def test_engine_connects():
    engine = make_engine(TEST_URL)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1
