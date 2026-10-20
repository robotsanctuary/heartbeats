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


def test_share_buttons_on_animal_page(site):
    out, _ = site
    page = (out / "animals/A1.html").read_text()
    for needle in ("sms:?&amp;body=", "mailto:?subject=", "facebook.com/sharer", "twitter.com/intent/tweet",
                   "wa.me/?text=", "Copy link", "More…"):
        assert needle in page, needle
    # share links carry the animal's own page, never the shelter's or a bare homepage
    assert "https%3A%2F%2Ffadingheartbeats.com%2Fanimals%2FA1.html" in page
    assert "Rex%20needs%20a%20way%20out%20of%20the%20shelter%20by%20tomorrow" in page


def test_share_text_matches_deadline(site):
    out, _ = site
    assert "foster%20home%20now" in (out / "animals/A2.html").read_text()  # no date -> foster now


def test_link_preview_tags(site):
    out, _ = site
    page = (out / "animals/A1.html").read_text()
    assert '<meta property="og:title" content="Can you help Rex?">' in page
    assert '<meta property="og:url" content="https://fadingheartbeats.com/animals/A1.html">' in page
    assert page.count('name="description"') == 1


def test_share_text_is_escaped(site):
    out, _ = site
    page = (out / "animals/A1.html").read_text()
    assert "<b>" not in page.split("<script>")[-1]


def test_shelter_page_lists_only_that_shelters_animals(site):
    out, res = site
    page = (out / "tx/dallas/index.html").read_text()
    assert ">Rex<" in page and ">Pup<" in page
    assert ">Else<" not in page                     # unregistered shelter's animal
    assert ">Gone<" not in page and ">Limbo<" not in page
    assert 'href="../../animals/A1.html"' in page   # links work from two folders down
    assert 'src="../../img/' in page or "noimg" in page
    assert res["shelter_pages"] >= 1


def test_main_list_has_shelter_picker_and_keeps_everyone(site):
    out, _ = site
    idx = (out / "index.html").read_text()
    assert 'value="tx/dallas/index.html"' in idx and 'optgroup label="Texas"' in idx
    assert ">Else<" in idx                          # unregistered shelters still listed on the main page
    assert "Dallas Animal Services" in idx          # shelter shown on each card


def test_detail_links_to_its_shelter_page(site):
    out, _ = site
    assert 'href="../tx/dallas/index.html"' in (out / "animals/A1.html").read_text()
    assert "tx/dallas" not in (out / "animals/B1.html").read_text()
