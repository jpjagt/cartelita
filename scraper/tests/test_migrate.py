from sqlalchemy import text, inspect
from cartelera.migrate import apply_migrations


def test_migrations_create_expected_tables(engine):
    apply_migrations(engine)
    tables = set(inspect(engine).get_table_names())
    expected = {
        "category", "city", "venue", "venue_category", "event",
        "event_category", "event_translation", "list", "list_venue",
        "schema_migrations",
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


def test_list_venue_allows_null_whitelist(session):
    from sqlalchemy import text
    session.execute(text("INSERT INTO city (slug,name) VALUES ('bcn','BCN')"))
    session.execute(text("INSERT INTO venue (slug,name,city_id) VALUES ('v','V',1)"))
    session.execute(text("INSERT INTO list (slug,name,city_id) VALUES ('jazz','Jazz',1)"))
    # NULL whitelist must be allowed (means "all categories")
    session.execute(text(
        "INSERT INTO list_venue (list_id,venue_id,whitelist_category_id) VALUES (1,1,NULL)"))
    session.commit()
    n = session.execute(text("SELECT count(*) FROM list_venue")).scalar()
    assert n == 1
