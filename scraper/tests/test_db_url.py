from cartelera.db import _to_psycopg

_DIALECT = "postgresql+psycopg://"


def test_rewrites_postgresql_scheme():
    out = _to_psycopg("postgresql://u:p@host:5432/db")
    assert out == f"{_DIALECT}u:p@host:5432/db"


def test_rewrites_bare_postgres_scheme():
    # Coolify / Heroku-style URLs use the `postgres://` scheme, which SQLAlchemy
    # rejects (no `postgres` dialect). It must be normalized like `postgresql://`.
    out = _to_psycopg("postgres://u:p@host:5432/db")
    assert out == f"{_DIALECT}u:p@host:5432/db"


def test_already_psycopg_is_unchanged():
    url = f"{_DIALECT}u:p@host:5432/db"
    assert _to_psycopg(url) == url


def test_does_not_touch_password_containing_scheme_text():
    # Only the leading scheme is rewritten, not occurrences elsewhere.
    url = "postgresql://u:postgres@host:5432/db"
    assert _to_psycopg(url) == f"{_DIALECT}u:postgres@host:5432/db"
