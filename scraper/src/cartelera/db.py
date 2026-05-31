import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


def _url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    # SQLAlchemy + psycopg 3 dialect
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def make_engine(url: str | None = None):
    return create_engine(url and url.replace("postgresql://", "postgresql+psycopg://", 1) or _url())


def make_session_factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(url), expire_on_commit=False)
