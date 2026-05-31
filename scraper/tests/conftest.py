import os
import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from cartelera.db import make_engine

TEST_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5432/cartelera_test")


@pytest.fixture(scope="session")
def engine():
    return make_engine(TEST_URL)


@pytest.fixture()
def session(engine):
    """A session with a clean schema applied per test."""
    # Deferred import: cartelera.migrate is created in a later task; importing it
    # at module top would break collection until then.
    from cartelera.migrate import apply_migrations

    # Drop and recreate public schema for full isolation.
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    apply_migrations(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    s = factory()
    try:
        yield s
    finally:
        s.close()
