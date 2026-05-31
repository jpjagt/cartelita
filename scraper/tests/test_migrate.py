from sqlalchemy import text, inspect
from cartelera.migrate import apply_migrations


def test_migrations_create_expected_tables(engine):
    apply_migrations(engine)
    tables = set(inspect(engine).get_table_names())
    expected = {
        "category", "city", "venue", "venue_category", "event",
        "event_category", "list", "list_venue", "schema_migrations",
    }
    assert expected.issubset(tables)


def test_migrations_are_idempotent(engine):
    apply_migrations(engine)
    second = apply_migrations(engine)
    assert second == []  # nothing new applied the second time


def test_source_url_is_not_unique(engine):
    apply_migrations(engine)
    indexes = inspect(engine).get_indexes("event")
    for idx in indexes:
        assert idx["column_names"] != ["source_url"], "source_url must not be unique"
