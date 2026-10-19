"""Database layer: setup, timestamps, schema rules, trigger."""

import sqlite3
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

import db

CHI = ZoneInfo("America/Chicago")


def test_init_is_idempotent():
    db.init_db()
    db.init_db()
    with db.session() as c:
        tables = {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"pets", "media_sources", "pending_profiles", "audit_log", "publish_state"} <= tables


def test_pragmas(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()["foreign_keys"] == 1
    assert conn.execute("PRAGMA journal_mode").fetchone()["journal_mode"] == "wal"


def test_relative_db_path_resolves_to_repo(monkeypatch):
    monkeypatch.setenv("LOCAL_DB_PATH", "data/x.db")
    assert db.db_path() == db.REPO_DIR / "data" / "x.db"


@pytest.mark.parametrize("value,tz,expected", [
    # Dallas midnight in summer (CDT, UTC-5) and winter (CST, UTC-6)
    (datetime(2026, 8, 2), CHI, "2026-08-02T05:00:00.000Z"),
    (datetime(2026, 12, 2), CHI, "2026-12-02T06:00:00.000Z"),
    (date(2026, 8, 2), CHI, "2026-08-02T05:00:00.000Z"),
    ("2026-08-02", timezone.utc, "2026-08-02T00:00:00.000Z"),
    ("2026-08-02T17:00:00Z", timezone.utc, "2026-08-02T17:00:00.000Z"),
    ("2026-08-02T17:00:00-05:00", timezone.utc, "2026-08-02T22:00:00.000Z"),
    ("tomorrow 5pm", timezone.utc, None),
    ("", timezone.utc, None),
    (None, timezone.utc, None),
])
def test_to_utc(value, tz, expected):
    assert db.to_utc(value, assume_tz=tz) == expected


def test_utcnow_format_matches_schema_default(conn):
    now_py = db.utcnow()
    now_sql = conn.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now') AS t").fetchone()["t"]
    assert len(now_py) == len(now_sql) == 24
    assert now_py[:16] == now_sql[:16]


def test_parse_ts_roundtrip():
    s = "2026-08-02T05:00:00.000Z"
    assert db.parse_ts(s).astimezone(CHI).strftime("%Y-%m-%d %H:%M") == "2026-08-02 00:00"


def _pet(conn, **kw):
    row = {"pet_id": "A1", "shelter_name": "Dallas Animal Services", **kw}
    cols = ", ".join(row)
    conn.execute(f"INSERT INTO pets ({cols}) VALUES ({', '.join('?' * len(row))})", tuple(row.values()))


@pytest.mark.parametrize("col,bad", [
    ("deadline_timestamp", "2026-08-02"),           # date only
    ("deadline_timestamp", "2026-08-02T00:00:00-05:00"),  # not UTC/Z
    ("intake_date", "08/02/2026"),
    ("status", "DEAD"),
    ("species", "dog"),
])
def test_schema_rejects_bad_values(conn, col, bad):
    with pytest.raises(sqlite3.IntegrityError):
        _pet(conn, **{col: bad})


def test_schema_accepts_good_row(conn):
    _pet(conn, deadline_timestamp="2026-08-02T05:00:00.000Z", status="AT_RISK", species="DOG")
    assert conn.execute("SELECT count(*) n FROM pets").fetchone()["n"] == 1


def test_publish_state_single_row(conn):
    conn.execute("INSERT INTO publish_state (id, last_published_at) VALUES (1, NULL)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO publish_state (id) VALUES (2)")


def test_media_cascade_delete(conn):
    _pet(conn)
    conn.execute("INSERT INTO media_sources (pet_id, platform, url) VALUES ('A1','x','u')")
    conn.execute("DELETE FROM pets WHERE pet_id='A1'")
    assert conn.execute("SELECT count(*) n FROM media_sources").fetchone()["n"] == 0


def test_media_requires_existing_pet(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO media_sources (pet_id, platform, url) VALUES ('NOPE','x','u')")


def test_trigger_bumps_updated_at_only_for_published_fields(conn):
    _pet(conn, name="Rex")
    conn.execute("UPDATE pets SET updated_at = '2000-01-01T00:00:00.000Z'")
    # bookkeeping-only changes: no bump
    conn.execute("UPDATE pets SET last_seen_in_scrape_at = '2026-01-01T00:00:00.000Z', local_image_path = 'x.jpg'")
    assert conn.execute("SELECT updated_at FROM pets").fetchone()["updated_at"] == "2000-01-01T00:00:00.000Z"
    # same value re-written: no bump
    conn.execute("UPDATE pets SET name = 'Rex'")
    assert conn.execute("SELECT updated_at FROM pets").fetchone()["updated_at"] == "2000-01-01T00:00:00.000Z"
    # published field changed: bump
    conn.execute("UPDATE pets SET status = 'ADOPTED'")
    assert conn.execute("SELECT updated_at FROM pets").fetchone()["updated_at"] > "2026"
    # NULL -> value counts as a change
    conn.execute("UPDATE pets SET updated_at = '2000-01-01T00:00:00.000Z'")
    conn.execute("UPDATE pets SET breed = 'Lab'")
    assert conn.execute("SELECT updated_at FROM pets").fetchone()["updated_at"] > "2026"


def test_session_rolls_back_on_error():
    with pytest.raises(RuntimeError):
        with db.session() as c:
            _pet(c)
            raise RuntimeError("boom")
    with db.session() as c:
        assert c.execute("SELECT count(*) n FROM pets").fetchone()["n"] == 0


def test_cli_info_runs(capsys, monkeypatch):
    import runpy
    monkeypatch.setattr("sys.argv", ["db.py", "info"])
    runpy.run_path(str(db.REPO_DIR / "db.py"), run_name="__main__")
    assert "pets" in capsys.readouterr().out
