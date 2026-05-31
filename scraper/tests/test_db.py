from sqlalchemy import text


def test_engine_connects(engine):
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1
