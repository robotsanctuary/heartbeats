"""Scheduled runner: run log, quiet success, failure alert, daily summary."""

import json
from datetime import datetime, timedelta, timezone

import pytest

import db
import run_scheduled as rs
from conftest import feed_xml, item_xml


@pytest.fixture(autouse=True)
def runlog(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_LOG_PATH", str(tmp_path / "runs.jsonl"))


def test_success_is_logged_and_quiet(fake_feeds, fake_images):
    recs = rs.run_all()
    assert recs[0]["ok"] and rs.failure_alert(recs) == ""
    lines = rs.run_log_path().read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["result"]["fetched"] > 0


def test_failure_is_logged_and_alerts(monkeypatch, fake_images):
    from shelters.texas import dallas
    monkeypatch.setattr(dallas, "fetch_xml", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("feed down")))
    recs = rs.run_all()
    assert not recs[0]["ok"]
    alert = rs.failure_alert(recs)
    assert "FAILED" in alert and "feed down" in alert
    assert json.loads(rs.run_log_path().read_text())["ok"] is False


def test_unknown_category_warning_captured(fake_feeds, fake_images):
    fake_feeds.prelab = feed_xml(item_xml("A1", outcome="WEIRD"))
    fake_feeds.neonate = feed_xml()
    rec = rs.run_all()[0]
    assert any("WEIRD" in w for w in rec["warnings"])
    assert "WEIRD" in rs.build_summary()


def test_summary_content(fake_feeds, fake_images, conn):
    now = datetime.now(timezone.utc)
    today = now.astimezone(rs.LOCAL_TZ)
    tomorrow = today + timedelta(days=1)
    fake_feeds.prelab = feed_xml(
        item_xml("T1", name="Todd", deadline=today.strftime("%m/%d/%Y")),
        item_xml("T2", name="Tess", deadline=tomorrow.strftime("%m/%d/%Y")),
        item_xml("L1", name="Later", deadline=(today + timedelta(days=9)).strftime("%m/%d/%Y")),
        item_xml("O1", name="Old", deadline=(today - timedelta(days=3)).strftime("%m/%d/%Y")),
    )
    fake_feeds.neonate = feed_xml()
    rs.run_all()
    s = rs.build_summary()
    assert "4 at risk" in s and "+4 new" in s
    assert "2 deadline today/tomorrow" in s and "Todd T1" in s and "— today" in s and "Tess T2" in s and "— tomorrow" in s
    assert "Later" not in s
    assert "1 still listed past their deadline" in s
    assert "1 ok" in s and "expected 3" in s


def test_summary_counts_outcomes_of_older_pets(fake_feeds, fake_images, conn):
    fake_feeds.prelab = feed_xml(item_xml("A1"), item_xml("A2"))
    fake_feeds.neonate = feed_xml()
    rs.run_all()
    old = db._fmt(datetime.now(timezone.utc) - timedelta(days=3))
    conn.execute("UPDATE pets SET created_at = ?", (old,)); conn.commit()
    fake_feeds.prelab = feed_xml(item_xml("A1", outcome="ADOPTION"), item_xml("A2"))
    rs.run_all()
    s = rs.build_summary()
    assert "1 adopted" in s and "+0 new" in s


def test_summary_on_empty_db():
    s = rs.build_summary()
    assert "0 at risk" in s and "0 ok" in s
