from pathlib import Path
from sqlalchemy import text
from sqlalchemy.engine import Engine

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"


def _ensure_table(conn):
    conn.execute(text(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    ))


def applied_migrations(conn) -> set[str]:
    _ensure_table(conn)
    rows = conn.execute(text("SELECT filename FROM schema_migrations")).fetchall()
    return {r[0] for r in rows}


def apply_migrations(engine: Engine) -> list[str]:
    """Apply pending .sql files in filename order. Returns applied filenames."""
    files = sorted(p for p in MIGRATIONS_DIR.glob("*.sql"))
    newly_applied: list[str] = []
    with engine.begin() as conn:
        done = applied_migrations(conn)
        for path in files:
            if path.name in done:
                continue
            conn.execute(text(path.read_text()))
            conn.execute(
                text("INSERT INTO schema_migrations (filename) VALUES (:f)"),
                {"f": path.name},
            )
            newly_applied.append(path.name)
    return newly_applied
