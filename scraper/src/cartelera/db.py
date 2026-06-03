from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import sessionmaker, Session
from decouple import config

_PSYCOPG_PREFIX = "postgresql+psycopg://"


def _to_psycopg(url: str) -> str:
    """Rewrite a plain postgresql:// URL to the psycopg 3 dialect."""
    return url.replace("postgresql://", _PSYCOPG_PREFIX, 1)


def _url() -> str:
    url = config("DATABASE_URL")
    return _to_psycopg(url)


def ensure_database_exists(url: str | None = None) -> bool:
    """Create the target database if it does not already exist.

    Connects to the server's default `postgres` maintenance DB to issue a
    `CREATE DATABASE` (which can't run inside a transaction, hence AUTOCOMMIT).
    Returns True if the database was created, False if it already existed.
    """
    resolved = _to_psycopg(url) if url else _url()
    target = make_url(resolved)
    dbname = target.database
    if not dbname:
        return False
    # Connect to the maintenance DB on the same server with the same credentials.
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": dbname}
            ).scalar()
            if exists:
                return False
            # dbname comes from our own config, not user input; quote defensively.
            conn.execute(text(f'CREATE DATABASE "{dbname}"'))
            return True
    except (OperationalError, ProgrammingError):
        # Server unreachable or no permission to create — let the caller's own
        # connection surface the real error instead of masking it here.
        return False
    finally:
        admin.dispose()


def make_engine(url: str | None = None) -> Engine:
    resolved = _to_psycopg(url) if url else _url()
    return create_engine(resolved)


def make_session_factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(url), expire_on_commit=False)
