"""
db.py

The LOCAL database layer (SQLite). Every local script -- scrapers,
matching, review, publish's read side -- goes through here instead of
opening its own connection, so connection settings and timestamp
handling live in exactly one place.

Database file: LOCAL_DB_PATH in .env (relative paths are resolved
against this repo's folder, not the current directory). Defaults to
./data/heartbeats.db.

Timestamps: every timestamp column holds UTC text in ONE canonical
format, e.g. 2026-08-02T05:00:00.000Z (see TS_FORMAT_NOTE in
schema.sql). One fixed format means plain string comparison sorts
correctly, which the publish watermark and grace-period checks rely
on. Always write timestamps via utcnow() / to_utc() -- the schema's
CHECK constraints reject anything else.

Usage:
    from db import session, utcnow
    with session() as conn:
        rows = conn.execute("SELECT * FROM pets WHERE status = ?", ("AT_RISK",)).fetchall()

    python db.py init      # create the database + tables (safe to re-run)
    python db.py info      # show path and row counts
"""

import os
import sqlite3
import sys
from contextlib import contextmanager
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Optional, Union
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

REPO_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = REPO_DIR / "schema.sql"
DEFAULT_DB_PATH = "data/heartbeats.db"

load_dotenv(REPO_DIR / ".env")


def db_path() -> Path:
    """Read at call time (not import time) so tests/scripts can override it."""
    p = Path(os.environ.get("LOCAL_DB_PATH") or DEFAULT_DB_PATH).expanduser()
    return p if p.is_absolute() else REPO_DIR / p


def _dict_row(cursor, row):
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


def connect(path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    path = Path(path) if path else db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = _dict_row
    conn.execute("PRAGMA foreign_keys = ON")      # off by default in SQLite -- needed for ON DELETE CASCADE
    conn.execute("PRAGMA busy_timeout = 30000")   # wait (don't fail) if another script is mid-write
    conn.execute("PRAGMA journal_mode = WAL")     # readers don't block the scraper's writes
    return conn


@contextmanager
def session(path: Optional[Union[str, Path]] = None):
    """Open, commit on success, roll back on any error, always close."""
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: Optional[Union[str, Path]] = None) -> Path:
    """Create all tables/triggers if missing. Idempotent."""
    target = Path(path) if path else db_path()
    with session(target) as conn:
        conn.executescript(SCHEMA_PATH.read_text())
    return target


# ---------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------

def _fmt(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def utcnow() -> str:
    return _fmt(datetime.now(timezone.utc))


def to_utc(value, assume_tz: Union[ZoneInfo, timezone] = timezone.utc) -> Optional[str]:
    """
    Normalize a datetime / date / ISO-8601 string to the canonical UTC
    text format. Values without a timezone are interpreted in
    `assume_tz` (pass the shelter's own zone -- a bare "8/2" means
    midnight in Dallas, not midnight UTC). Returns None for empty or
    unparseable input rather than storing something wrong.
    """
    if value is None or value == "":
        return None
    if isinstance(value, str):
        s = value.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            value = datetime.fromisoformat(s)
        except ValueError:
            return None
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, time.min)
    if value.tzinfo is None:
        value = value.replace(tzinfo=assume_tz)
    return _fmt(value)


def parse_ts(value: Optional[str]) -> Optional[datetime]:
    """Canonical text -> aware datetime (UTC), for display/formatting."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "info"
    if cmd == "init":
        print(f"Initialized {init_db()}")
    elif cmd == "info":
        p = db_path()
        print(f"LOCAL_DB_PATH -> {p} ({'exists' if p.exists() else 'not created yet -- run: python db.py init'})")
        if p.exists():
            with session() as conn:
                for t in ("pets", "media_sources", "pending_profiles", "audit_log", "publish_state"):
                    print(f"  {t:<18} {conn.execute(f'SELECT count(*) AS n FROM {t}').fetchone()['n']}")
    else:
        sys.exit("usage: python db.py [init|info]")
