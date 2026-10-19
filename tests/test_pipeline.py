"""Images, social matching (fake LLM), review/promote, accuracy report, publish."""

import json
from types import SimpleNamespace

import pytest

import db
import image_archive
import matching_logic as ml
import promote_pending
import publish
from conftest import FakeResponse
from matching_logic import SocialPost


def add_pet(conn, pet_id="A1", status="AT_RISK", **kw):
    row = {"pet_id": pet_id, "shelter_name": "Dallas Animal Services", "status": status,
           "name": "Diesel", "breed": "Pit mix", **kw}
    conn.execute(f"INSERT INTO pets ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})", tuple(row.values()))
    conn.commit()


POST = SocialPost(platform="instagram", url="https://instagram.com/p/1", posted_by="@vol", raw_text="Diesel A1")


def extraction(**kw):
    base = {"pet_id": None, "deadline": None, "shelter_name": "Dallas Animal Services",
            "animal_name": None, "animal_description": "3yo pit mix", "confidence": 0.9}
    return {**base, **kw}


def n(conn, table, where="1=1"):
    return conn.execute(f"SELECT count(*) c FROM {table} WHERE {where}").fetchone()["c"]


# ------------------------------------------------------------------ images

def test_archive_image_saves_and_reuses(fake_images):
    p1 = image_archive.archive_image("A1", "https://x/image/A1/DLLS/1")
    p2 = image_archive.archive_image("A1", "https://x/image/A1/DLLS/1")
    assert p1 == p2 and p1.endswith("A1.jpg") and len(fake_images) == 1
    assert not list(image_archive.image_dir().glob("*.part"))


@pytest.mark.parametrize("pet_id,url,name", [
    ("../../etc/passwd", "https://x/a.png", "______etc_passwd.png"),
    ("A1", "https://x/page.php", "A1.jpg"),
    ("A1", "https://x/pic.JPEG", "A1.jpeg"),
])
def test_archive_image_safe_names(fake_images, pet_id, url, name):
    path = image_archive.archive_image(pet_id, url)
    assert path.endswith("/" + name)
    assert str(image_archive.image_dir()) in path


def test_archive_image_rejects_non_image(monkeypatch):
    monkeypatch.setattr(image_archive.requests, "get",
                        lambda *a, **k: FakeResponse(b"<html>", "text/html"))
    with pytest.raises(ValueError):
        image_archive.archive_image("A1", "https://x/1")
    assert not list(image_archive.image_dir().glob("*"))


def test_cleanup_retention_rules(conn, tmp_path):
    files = {}
    for pid, status in [("E", "EUTHANIZED"), ("S", "ADOPTED"), ("R", "AT_RISK"), ("X", "ARCHIVED")]:
        f = tmp_path / f"{pid}.jpg"; f.write_bytes(b"x"); files[pid] = f
        add_pet(conn, pid, status, local_image_path=str(f))
    result = image_archive.cleanup_resolved_images(conn)
    conn.commit()
    assert result == {"archived_permanently": 1, "deleted": 2, "left_open": 1}
    assert files["E"].exists() and files["R"].exists()
    assert not files["S"].exists() and not files["X"].exists()
    assert conn.execute("SELECT image_permanently_archived a FROM pets WHERE pet_id='E'").fetchone()["a"] == 1


# ------------------------------------------------------------------ matching

def test_exact_id_match_appends_media(conn):
    add_pet(conn)
    r = ml.process_extraction(extraction(pet_id="A1"), POST)
    assert r["action"] == "APPENDED_TO_EXISTING_PET"
    assert n(conn, "media_sources") == 1 and n(conn, "audit_log", "action='APPENDED_TO_EXISTING_PET'") == 1
    ml.process_extraction(extraction(pet_id="A1"), POST)       # same post again
    assert n(conn, "media_sources") == 1                      # no duplicate


def test_unknown_id_creates_pending(conn):
    r = ml.process_extraction(extraction(pet_id="A999", deadline="2026-08-02", confidence=0.6), POST)
    assert r == {"action": "CREATED_PENDING_PROFILE", "extracted_pet_id": "A999", "needs_review": True}
    row = conn.execute("SELECT * FROM pending_profiles").fetchone()
    assert row["needs_review"] == 1 and row["deadline_guess"] == "2026-08-02T00:00:00.000Z"


def test_garbage_deadline_from_model_stored_as_null(conn):
    ml.process_extraction(extraction(pet_id="A999", deadline="next tuesday"), POST)
    assert conn.execute("SELECT deadline_guess d FROM pending_profiles").fetchone()["d"] is None


def test_low_confidence_flagged(conn):
    r = ml.process_extraction(extraction(pet_id="A1", confidence=0.2), POST)
    assert r["action"] == "FLAGGED_FOR_REVIEW"
    assert n(conn, "pending_profiles", "needs_review=1") == 1


def test_no_description_creates_pending(conn):
    r = ml.process_extraction(extraction(animal_description=None), POST)
    assert r["reason"] == "no_description"


def test_no_candidates_creates_pending(conn):
    r = ml.process_extraction(extraction(), POST)
    assert r["reason"] == "no_candidates"


def fake_llm(monkeypatch, pet_id, prob, seen=None):
    def create(**kwargs):
        if seen is not None:
            seen.append(kwargs)
        content = json.dumps({"best_match_pet_id": pet_id, "probability": prob, "reasoning": "test"})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    monkeypatch.setattr(ml.client.chat.completions, "create", create)


@pytest.mark.parametrize("prob,action", [
    (0.95, "FUZZY_MATCHED_AND_MERGED"),
    (0.70, "FLAGGED_FOR_REVIEW"),
    (0.30, "CREATED_PENDING_PROFILE"),
])
def test_fuzzy_bands(conn, monkeypatch, prob, action):
    add_pet(conn)
    fake_llm(monkeypatch, "A1", prob)
    r = ml.process_extraction(extraction(), POST)
    assert r["action"] == action
    assert n(conn, "media_sources") == (1 if action == "FUZZY_MATCHED_AND_MERGED" else 0)
    assert n(conn, "audit_log", "stage='fuzzy_match'") == 1


def test_fuzzy_llm_hallucinated_id_is_not_merged(conn, monkeypatch):
    add_pet(conn)
    fake_llm(monkeypatch, "NOT-A-CANDIDATE", 0.99)
    r = ml.process_extraction(extraction(), POST)
    assert r["action"] == "CREATED_PENDING_PROFILE" and n(conn, "media_sources") == 0


def test_fuzzy_candidates_scoped_and_case_insensitive(conn, monkeypatch):
    add_pet(conn, "A1")
    add_pet(conn, "B1", shelter_name="Other Shelter")
    add_pet(conn, "A2", status="ADOPTED")
    seen = []
    fake_llm(monkeypatch, None, 0.0, seen)
    ml.process_extraction(extraction(shelter_name="dallas animal"), POST)
    prompt = seen[0]["messages"][1]["content"]
    assert '"A1"' in prompt and '"B1"' not in prompt and '"A2"' not in prompt


def test_fuzzy_shelter_name_wildcards_escaped(conn, monkeypatch):
    add_pet(conn)
    fake_llm(monkeypatch, None, 0.0)
    r = ml.process_extraction(extraction(shelter_name="%"), POST)
    assert r["reason"] == "no_candidates"


# ------------------------------------------------------------------ review

def test_promote_and_reject(conn):
    ml.process_extraction(extraction(pet_id="A5", confidence=0.6), POST)
    pid = conn.execute("SELECT id FROM pending_profiles").fetchone()["id"]
    promote_pending.promote(pid, "A5", "Dallas Animal Services")
    assert n(conn, "pets", "pet_id='A5'") == 1 and n(conn, "media_sources") == 1
    assert n(conn, "pending_profiles") == 0
    assert n(conn, "audit_log", "human_verdict='correct' AND reviewed_at IS NOT NULL") == 1

    post2 = SocialPost("x", "https://x.com/2", None, "junk")
    ml.process_extraction(extraction(pet_id="Z9", confidence=0.6), post2)
    pid2 = conn.execute("SELECT id FROM pending_profiles").fetchone()["id"]
    promote_pending.reject(pid2)
    assert n(conn, "pending_profiles") == 0 and n(conn, "audit_log", "human_verdict='incorrect'") == 1


def test_promote_missing_id_raises():
    with pytest.raises(ValueError):
        promote_pending.promote("nope", "A1", "X")


def test_accuracy_report_runs(conn, monkeypatch, capsys):
    import runpy
    ml.process_extraction(extraction(pet_id="A9", confidence=0.6), POST)
    conn.execute("UPDATE audit_log SET human_verdict='correct'"); conn.commit()
    runpy.run_path(str(db.REPO_DIR / "accuracy_report.py"), run_name="__main__")
    out = capsys.readouterr().out
    assert "Review Queue (1 shown" in out and "1/1 reviewed" in out and "CREATED_PENDING_PROFILE" in out


# ------------------------------------------------------------------ publish

class FakeRemote:
    def __init__(self):
        self.calls = []

    def cursor(self):
        return self

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split())[:30], params))

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_publish_dry_run_needs_no_remote(conn):
    add_pet(conn)
    r = publish.publish(dry_run=True)
    assert r == {"pets": 1, "media_sources": 0, "photos": 0, "dry_run": True}


def test_publish_without_remote_config_fails_clearly(conn):
    add_pet(conn)
    with pytest.raises(RuntimeError, match="REMOTE_DATABASE_URL"):
        publish.publish()
    assert conn.execute("SELECT last_published_at l FROM publish_state").fetchone() is None


def test_publish_incremental_watermark(conn, monkeypatch, tmp_path):
    import time
    remote = FakeRemote()
    monkeypatch.setattr(publish, "get_remote_conn", lambda: remote)
    tick = lambda: time.sleep(0.005)   # keep writes and watermarks in distinct milliseconds
    add_pet(conn, "A1"); add_pet(conn, "A2"); tick()
    assert publish.publish()["pets"] == 2; tick()
    # nothing changed -> nothing sent
    assert publish.publish()["pets"] == 0; tick()
    # bookkeeping change -> still nothing
    conn.execute("UPDATE pets SET last_seen_in_scrape_at = ?", (db.utcnow(),)); conn.commit(); tick()
    assert publish.publish()["pets"] == 0; tick()
    # real change -> only that pet
    conn.execute("UPDATE pets SET status='ADOPTED' WHERE pet_id='A2'"); conn.commit(); tick()
    assert publish.publish()["pets"] == 1; tick()
    # a new social link on an unchanged pet still gets published (old bug)
    conn.execute("INSERT INTO media_sources (pet_id, platform, url) VALUES ('A1','x','https://x/9')"); conn.commit(); tick()
    r = publish.publish()
    assert r["pets"] == 0 and r["media_sources"] == 1; tick()
    # --full re-sends everything
    assert publish.publish(full=True)["pets"] == 2


def test_publish_same_millisecond_write_not_lost(conn, monkeypatch):
    """A row stamped exactly at the watermark must be published, not skipped."""
    remote = FakeRemote()
    monkeypatch.setattr(publish, "get_remote_conn", lambda: remote)
    add_pet(conn, "A1")
    publish.publish()
    wm = conn.execute("SELECT last_published_at w FROM publish_state").fetchone()["w"]
    conn.execute("INSERT INTO media_sources (pet_id, platform, url, created_at) VALUES ('A1','x','u',?)", (wm,))
    conn.commit()
    assert publish.publish()["media_sources"] == 1


def test_publish_memorial_photo_once(conn, monkeypatch, tmp_path):
    remote = FakeRemote()
    monkeypatch.setattr(publish, "get_remote_conn", lambda: remote)
    f = tmp_path / "E.jpg"; f.write_bytes(b"photo")
    add_pet(conn, "E", "EUTHANIZED", local_image_path=str(f), image_permanently_archived=1,
            euthanized_at=db.utcnow())
    assert publish.publish()["photos"] == 1
    assert conn.execute("SELECT remote_image_uploaded_at u FROM pets").fetchone()["u"] is not None
    assert publish.publish(full=True)["photos"] == 0


def test_publish_remote_failure_keeps_watermark(conn, monkeypatch):
    class Broken(FakeRemote):
        def execute(self, *a, **k):
            raise RuntimeError("remote down")
    monkeypatch.setattr(publish, "get_remote_conn", lambda: Broken())
    add_pet(conn)
    with pytest.raises(RuntimeError):
        publish.publish()
    assert conn.execute("SELECT * FROM publish_state").fetchone() is None
