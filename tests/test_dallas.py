"""Dallas scraper end to end against real captured feeds + edge cases."""

from datetime import datetime, timedelta, timezone

import pytest

import db
from conftest import feed_xml, item_xml
from shelters import common
from shelters.texas import dallas


def count(conn, where="1=1"):
    return conn.execute(f"SELECT count(*) n FROM pets WHERE {where}").fetchone()["n"]


def test_dry_run_writes_nothing(fake_feeds, fake_images, conn):
    result = dallas.run(write=False)
    assert result["written"] is False and result["fetched"] > 0
    assert count(conn) == 0 and fake_images == []


def test_real_feed_full_run(fake_feeds, fake_images, conn):
    expected = len(dallas.fetch_and_normalize())
    result = dallas.run(write=True)
    assert result["fetched"] == expected == result["inserted"]
    assert count(conn) == expected
    # every stored timestamp is canonical (the schema CHECK would have
    # rejected anything else, but make it explicit)
    for r in conn.execute("SELECT deadline_timestamp d, intake_date i FROM pets"):
        for v in (r["d"], r["i"]):
            assert v is None or (len(v) == 24 and v.endswith("Z"))
    # pre-lab deadlines are midnight Dallas time (05:00Z in CDT / 06:00Z in CST)
    hours = {r["d"][11:13] for r in conn.execute("SELECT deadline_timestamp d FROM pets WHERE d IS NOT NULL")}
    assert hours <= {"05", "06"}
    # images saved and linked
    assert count(conn, "local_image_path IS NOT NULL") == len(fake_images) > 0
    # descriptions have no leftover HTML
    assert count(conn, "description LIKE '%<BR>%'") == 0
    # all statuses valid and every pet seen this run
    assert count(conn, "last_seen_in_scrape_at IS NULL") == 0


def test_second_identical_run_is_unchanged(fake_feeds, fake_images, conn):
    dallas.run(write=True)
    before = {r["pet_id"]: r["updated_at"] for r in conn.execute("SELECT pet_id, updated_at FROM pets")}
    n_images = len(fake_images)
    r2 = dallas.run(write=True)
    assert r2["inserted"] == 0 and r2["updated"] == 0 and r2["unchanged"] == r2["fetched"]
    after = {r["pet_id"]: r["updated_at"] for r in conn.execute("SELECT pet_id, updated_at FROM pets")}
    assert before == after                      # nothing would be re-published
    assert len(fake_images) == n_images         # images not re-downloaded


def test_changed_field_detected(fake_feeds, fake_images, conn):
    fake_feeds.prelab = feed_xml(item_xml("A1", name="Rex"))
    fake_feeds.neonate = feed_xml()
    dallas.run(write=True)
    fake_feeds.prelab = feed_xml(item_xml("A1", name="Rex", deadline="08/05/2026"))
    r = dallas.run(write=True)
    assert r["updated"] == 1
    assert conn.execute("SELECT deadline_timestamp d FROM pets").fetchone()["d"] == "2026-08-05T05:00:00.000Z"


def test_outcome_mapping(fake_feeds, fake_images, conn, capsys):
    fake_feeds.prelab = feed_xml(
        item_xml("A1", outcome=""), item_xml("A2", outcome="ADOPTION"),
        item_xml("A3", outcome="TRANSFER"), item_xml("A4", outcome="RTO"),
        item_xml("A5", outcome="FOSTER"), item_xml("A6", outcome="SOMETHING NEW"),
        item_xml("A7", pathway="EM RESCUE"),
    )
    fake_feeds.neonate = feed_xml()
    dallas.run(write=True)
    st = {r["pet_id"]: r["status"] for r in conn.execute("SELECT pet_id, status FROM pets")}
    assert st == {"A1": "AT_RISK", "A2": "ADOPTED", "A3": "TRANSFERRED", "A4": "SAFE",
                  "A5": "SAFE", "A6": "PENDING_VERIFICATION", "A7": "AT_RISK"}
    out = capsys.readouterr().out
    assert "SOMETHING NEW" in out            # unknown outcome flagged loudly
    assert "EM RESCUE" not in out            # now a known pathway


def test_species_and_bad_dates(fake_feeds, fake_images, conn):
    fake_feeds.prelab = feed_xml(
        item_xml("C1", animal_type="Cat"), item_xml("R1", animal_type="Rabbit"),
        item_xml("D1", deadline="not a date", intake=""),
    )
    fake_feeds.neonate = feed_xml()
    dallas.run(write=True)
    rows = {r["pet_id"]: r for r in conn.execute("SELECT * FROM pets")}
    assert rows["C1"]["species"] == "CAT" and rows["R1"]["species"] == "OTHER"
    assert rows["D1"]["deadline_timestamp"] is None and rows["D1"]["intake_date"] is None


def test_item_without_id_is_skipped(fake_feeds, fake_images, conn):
    fake_feeds.prelab = feed_xml(item_xml("A1"), item_xml(""))
    fake_feeds.neonate = feed_xml()
    r = dallas.run(write=True)
    assert r["fetched"] == 1 and count(conn) == 1


def test_prelab_wins_over_neonate_duplicate(fake_feeds, fake_images, conn):
    fake_feeds.neonate = feed_xml(item_xml("A1", name="FromNeonate", deadline=""))
    fake_feeds.prelab = feed_xml(item_xml("A1", name="FromPrelab"))
    dallas.run(write=True)
    assert conn.execute("SELECT name FROM pets").fetchone()["name"] == "FromPrelab"


def test_missing_animals_archived_after_grace_period(fake_feeds, fake_images, conn):
    fake_feeds.prelab = feed_xml(item_xml("A1"), item_xml("A2"))
    fake_feeds.neonate = feed_xml()
    dallas.run(write=True)
    # A2 disappears, but was seen just now -> still inside the 12h grace period
    fake_feeds.prelab = feed_xml(item_xml("A1"))
    assert dallas.run(write=True)["archived"] == 0
    # pretend A2 was last seen 13 hours ago
    old = db._fmt(datetime.now(timezone.utc) - timedelta(hours=13))
    conn.execute("UPDATE pets SET last_seen_in_scrape_at = ? WHERE pet_id = 'A2'", (old,))
    conn.commit()
    assert dallas.run(write=True)["archived"] == 1
    st = {r["pet_id"]: r["status"] for r in conn.execute("SELECT pet_id, status FROM pets")}
    assert st == {"A1": "AT_RISK", "A2": "ARCHIVED"}   # never EUTHANIZED by inference


def test_empty_feed_never_archives_everything(fake_feeds, fake_images, conn):
    fake_feeds.prelab = feed_xml(item_xml("A1"))
    fake_feeds.neonate = feed_xml()
    dallas.run(write=True)
    old = db._fmt(datetime.now(timezone.utc) - timedelta(days=2))
    conn.execute("UPDATE pets SET last_seen_in_scrape_at = ?", (old,))
    conn.commit()
    fake_feeds.prelab = feed_xml()
    assert dallas.run(write=True)["archived"] == 0
    assert count(conn, "status='AT_RISK'") == 1


def test_other_shelters_untouched_by_archive(conn):
    conn.execute("INSERT INTO pets (pet_id, shelter_name) VALUES ('X1', 'Other Shelter')")
    conn.execute("INSERT INTO pets (pet_id, shelter_name) VALUES ('D1', 'Dallas Animal Services')")
    archived = common.mark_missing_as_resolved(conn, "Dallas Animal Services", ["D9"], grace_period_hours=0)
    assert archived == ["D1"]


def test_image_failure_does_not_block_ingest(fake_feeds, monkeypatch, conn):
    import image_archive
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(image_archive.requests, "get", boom)
    fake_feeds.prelab = feed_xml(item_xml("A1"), item_xml("A2"))
    fake_feeds.neonate = feed_xml()
    r = dallas.run(write=True)
    assert r["image_failures"] == 2 and count(conn) == 2


def test_feed_failure_writes_nothing(monkeypatch, fake_images, conn):
    def boom(url, timeout=30):
        raise RuntimeError("feed down")
    monkeypatch.setattr(dallas, "fetch_xml", boom)
    with pytest.raises(RuntimeError):
        dallas.run(write=True)
    assert count(conn) == 0


def test_upsert_requires_id_and_shelter(conn):
    with pytest.raises(ValueError):
        common.upsert_pet_local(conn, {"pet_id": None, "shelter_name": "X"})


def test_dd_agg_pathway_is_known_and_stays_listed(fake_feeds, fake_images, conn, capsys):
    # Seen live 2026-10-27 (3 Cane Corsos, no deadline). Owner chose to list them like any other at-risk animal.
    fake_feeds.prelab = feed_xml(item_xml("D1", pathway="DD/AGG"), item_xml("N1", pathway="BRAND NEW"))
    fake_feeds.neonate = feed_xml()
    dallas.run(write=True)
    st = {r["pet_id"]: r["status"] for r in conn.execute("SELECT pet_id, status FROM pets")}
    assert st["D1"] == "AT_RISK"
    out = capsys.readouterr().out
    assert "DD/AGG" not in out and "BRAND NEW" in out   # still loud about genuinely new values


@pytest.mark.parametrize("raw, want", [
    ("Sweet <BR>boy", "Sweet\nboy"),
    ("One.<br><br>Two.<br />Three.", "One.\n\nTwo.\nThree."),
    ("One.\r\n\r\nTwo.", "One.\n\nTwo."),
    ("  A   <b>bold</b>  word.\n\n\n\nB  ", "A bold word.\n\nB"),
    ("<p>Para one.</p><p>Para two.</p>", "Para one.\n\nPara two."),
    ("<br><br>", None),
])
def test_shelter_words_kept_with_their_paragraphs(raw, want):
    from shelters.common import strip_html
    assert strip_html(raw) == want


def test_detail_page_shows_shelter_paragraphs():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("bs_par", Path(__file__).resolve().parent.parent / "design" / "build_site.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    p = {"desc": "Tara is 8.\n\nShe needs help.\nCall us.", "name": "Tara", "days": 3}
    assert m.blurb(p["desc"]) == "Tara is 8. She needs help. Call us."           # card excerpt stays one line
    paras = [x.strip() for x in p["desc"].split("\n") if x.strip()]
    assert paras == ["Tara is 8.", "She needs help.", "Call us."]
