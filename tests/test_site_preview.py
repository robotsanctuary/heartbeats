"""Offline checks for design/build_site.py using a throwaway SQLite DB."""
import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

import db

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def site(tmp_path, monkeypatch):
    dbfile = tmp_path / "t.db"
    monkeypatch.setenv("LOCAL_DB_PATH", str(dbfile))
    db.init_db(dbfile)
    rows = [
        # pet_id, name, status, deadline, euthanized_at, shelter
        ("A1", "REX", "AT_RISK", "2026-10-20T05:00:00.000Z", None, "Dallas Animal Services"),
        ("A2", "PUP", "AT_RISK", None, None, "Dallas Animal Services"),
        ("A3", "GONE", "EUTHANIZED", None, "2026-10-18T05:00:00.000Z", "Dallas Animal Services"),
        ("A4", "SAFE", "ADOPTED", None, None, "Dallas Animal Services"),
        ("B1", "ELSE", "AT_RISK", "2026-10-21T05:00:00.000Z", None, "Unregistered Shelter"),
        ("A5", "LIMBO", "PENDING_VERIFICATION", None, None, "Dallas Animal Services"),
    ]
    with db.session(dbfile) as c:
        for pid, name, st, dl, eu, sh in rows:
            c.execute("""INSERT INTO pets (pet_id,name,status,deadline_timestamp,euthanized_at,shelter_name,description)
                         VALUES (?,?,?,?,?,?,?)""", (pid, name, st, dl, eu, sh, f"<b>{name}</b> story"))
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "design" / "build_site.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_site"] = mod
    spec.loader.exec_module(mod)
    out = tmp_path / "site"
    res = mod.build(out, today=date(2026, 10, 19))
    return out, res


def test_pages_exist(site):
    out, res = site
    for f in ("index.html", "help.html", "remembered.html", "animals/A1.html", "animals/A3.html"):
        assert (out / f).exists(), f
    assert res["at_risk"] == 3 and res["remembered"] == 1


def test_only_at_risk_on_list(site):
    out, _ = site
    idx = (out / "index.html").read_text()
    assert "Rex" in idx and "Pup" in idx
    for hidden in ("Gone", "Safe", "Limbo"):
        assert f">{hidden}<" not in idx


def test_memorial_is_only_euthanized(site):
    out, _ = site
    mem = (out / "remembered.html").read_text()
    assert "Gone" in mem
    for other in ("Rex", "Safe", "Limbo"):
        assert other not in mem


def test_adopt_button_goes_to_the_animals_own_shelter_page(site):
    out, _ = site
    assert "https://24petconnect.com/DallasAdoptions/Details/DLLS/A1" in (out / "animals/A1.html").read_text()


def test_unregistered_shelter_gets_no_button(site):
    out, res = site
    page = (out / "animals/B1.html").read_text()
    assert "Foster or adopt" not in page and "24petconnect" not in page
    assert res["no_adopt_link"] == 1


def test_descriptions_are_escaped(site):
    out, _ = site
    assert "<b>REX</b>" not in (out / "animals/A1.html").read_text()


def test_no_date_animals_grouped_last(site):
    out, _ = site
    idx = (out / "index.html").read_text()
    assert idx.index("Tomorrow") < idx.index("Needs a foster now")
