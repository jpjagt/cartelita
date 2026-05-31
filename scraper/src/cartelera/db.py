import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

_PSYCOPG_PREFIX = "postgresql+psycopg://"


def _to_psycopg(url: str) -> str:
    """Rewrite a plain postgresql:// URL to the psycopg 3 dialect."""
    return url.replace("postgresql://", _PSYCOPG_PREFIX, 1)


def _url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return _to_psycopg(url)


def make_engine(url: str | None = None) -> Engine:
    resolved = _to_psycopg(url) if url else _url()
    return create_engine(resolved)


def make_session_factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(url), expire_on_commit=False)
