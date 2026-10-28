"""Offline checks for design/build_site.py using a throwaway SQLite DB."""
import importlib.util
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo
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
    res = mod.build(out, today=date(2026, 10, 19), show_remembered=True, show_picker=True, show_dog=True)
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


def test_launch_defaults_hide_remembered_and_single_shelter_menu(site, tmp_path):
    import build_site
    out = tmp_path / "launch"
    res = build_site.build(out, today=date(2026, 10, 19), show_remembered=False, show_picker=None)
    assert not (out / "remembered.html").exists()
    assert not (out / "animals/A3.html").exists()          # memorial animals get no page either
    for f in ("index.html", "help.html", "animals/A1.html", "tx/dallas/index.html"):
        page = (out / f).read_text()
        assert "remembered.html" not in page and "Remembered" not in page, f
    idx = (out / "index.html").read_text()
    assert "Choose your shelter" not in idx                 # only one registered shelter
    assert 'class="where"' not in idx
    assert (out / "tx/dallas/index.html").exists()          # shelter page itself still built


def test_launch_defaults_ship_no_dog(site, tmp_path):
    import build_site
    out = tmp_path / "launch"
    build_site.build(out, today=date(2026, 10, 19), show_remembered=False, show_picker=None, show_dog=False)
    for f in ("index.html", "help.html", "animals/A1.html", "tx/dallas/index.html"):
        page = (out / f).read_text()
        assert 'class="dog"' not in page and "__dog" not in page and "dog.png" not in page, f
    left = sorted(str(p.relative_to(out)) for p in out.rglob("*") if "dog" in p.name.lower())
    assert left == []                                       # no sprite, engine or lab/test pages


def test_every_page_has_the_analytics_tag_once(site, tmp_path):
    import build_site
    out = tmp_path / "launch"
    build_site.build(out, today=date(2026, 10, 19), show_remembered=False, show_picker=None, show_dog=False)
    for root in (site[0], out):                             # everything on and launch defaults
        pages = list(root.rglob("*.html"))
        assert len(pages) > 3
        for f in pages:
            page = f.read_text()
            assert page.count("googletagmanager.com/gtag/js?id=G-F98F38JQ09") == 1, f
            assert page.count("gtag('config', 'G-F98F38JQ09')") == 1, f
            assert page.index("gtag/js") < page.index("</head>"), f


def test_analytics_never_doubles_and_headless_page_fails(site, tmp_path):
    import build_site
    f = tmp_path / "x.html"
    f.write_text('<!doctype html><html><HEAD lang="en"><title>x</title></head><body></body></html>')
    build_site.add_analytics(f)
    build_site.add_analytics(f)
    assert f.read_text().count("gtag/js?id=G-F98F38JQ09") == 1
    f.write_text("<p>no head here</p>")
    with pytest.raises(ValueError):
        build_site.add_analytics(f)


def test_dog_switch_is_off_unless_asked(monkeypatch):
    spec = importlib.util.spec_from_file_location("bs_env", ROOT / "design" / "build_site.py")
    for env, want in ((None, False), ("0", False), ("1", True)):
        if env is None:
            monkeypatch.delenv("SHOW_DOG", raising=False)
        else:
            monkeypatch.setenv("SHOW_DOG", env)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.SHOW_DOG is want, env


def test_brand_assets_and_logo(site):
    out, _ = site
    assert (out / "icon.svg").exists() and (out / "og.png").exists()
    idx = (out / "index.html").read_text()
    assert 'rel="icon" href="icon.svg"' in idx and 'class="beat"' in idx
    assert 'href="../../icon.svg"' in (out / "tx/dallas/index.html").read_text()
    assert "prefers-reduced-motion" in idx           # animations switch off for reduced-motion users


def test_home_band_and_full_width_topbar(site):
    out, _ = site
    idx = (out / "index.html").read_text()
    assert idx.index('class="topbar"') < idx.index('class="band"') < idx.index('class="wrap')  # full-width, outside the column
    assert 'href="#list"' in idx and 'id="list"' in idx
    assert 'class="band"' not in (out / "help.html").read_text()


def test_spotlight_features_only_todays_animals(site):
    import build_site as m
    from datetime import date as d
    img = Path(__file__)
    def pet(n, days, has_img=True):
        return {"name": n, "days": days, "img": img if has_img else None,
                "deadline": d(2026, 10, 20 + max(days or 0, 0))}
    pets = [pet("Later", 2), pet("Zed", 0), pet("NoPhoto", 0, False), pet("Past", -1), pet("Baby", None), pet("Amy", 0)]
    picks, label = m.spot_pets(pets)
    assert [p["name"] for p in picks] == ["Amy", "Zed", "NoPhoto"]   # today only, photos first
    assert label == "Out of time today"
    picks, label = m.spot_pets([pet("Later", 2), pet("Soon", 1), pet("Baby", None)])
    assert [p["name"] for p in picks] == ["Soon"] and label == "Out of time tomorrow"   # nobody today -> next day
    assert m.spot_pets([pet("Baby", None), pet("Past", -2)]) == ([], "")


def test_home_spotlight_rendered(site):
    out, _ = site
    idx = (out / "index.html").read_text()
    # fixture "today" is 2026-10-19; Rex is due 10-20 (tomorrow) and is the only one -> featured, no dots
    assert 'class="spot"' in idx and "Out of time tomorrow" in idx and 'class="slide on" href="animals/A1.html"' in idx
    assert 'class="spot"' not in (out / "tx/dallas/index.html").read_text()


def test_scrolling_dog_on_every_page_and_off_for_reduced_motion(site):
    out, _ = site
    for f in ("index.html", "help.html", "animals/A1.html", "tx/dallas/index.html"):
        page = (out / f).read_text()
        assert 'class="dog"' in page and 'aria-hidden="true"' in page.split('class="dog"')[1][:40], f
    idx = (out / "index.html").read_text()
    assert ".dog{display:none!important}" in idx.split("prefers-reduced-motion:reduce")[1][:80]  # CSS off
    assert 'matchMedia("(prefers-reduced-motion: reduce)").matches){d.remove()' in idx           # JS off
    assert (out / "dog.png").exists() and "url(dog.png)" in idx
    assert "url(../../dog.png)" in (out / "tx/dallas/index.html").read_text()           # path works 2 folders down


def test_every_page_says_when_it_was_built(site, tmp_path):
    import build_site
    out = tmp_path / "stamped"
    at = datetime(2026, 10, 27, 21, 2, 30, tzinfo=ZoneInfo("America/Chicago"))
    res = build_site.build(out, today=date(2026, 10, 27), show_remembered=False, show_dog=False, built_at=at)
    assert res["built"] == "2026-10-28T02:02:30Z"
    for f in out.rglob("*.html"):
        page = f.read_text()
        assert "Updated Oct 27, 9:02 PM CT" in page, f
        assert '<meta name="hb-built" content="2026-10-28T02:02:30Z">' in page, f


def test_launch_pages_have_no_draft_tags_and_link_privacy(site, tmp_path):
    import build_site
    out = tmp_path / "launch"
    build_site.build(out, today=date(2026, 10, 19), show_remembered=False, show_dog=False)
    pages = list(out.rglob("*.html"))
    assert out / "privacy.html" in pages
    for f in pages:
        page = f.read_text()
        assert "[draft]" not in page, f
        assert 'privacy.html">Privacy</a>' in page, f
    assert 'href="../../privacy.html"' in (out / "tx/dallas/index.html").read_text()   # works 2 folders down


def test_privacy_page_discloses_analytics(site):
    out, _ = site
    p = (out / "privacy.html").read_text()
    for must in ("We use Google Analytics", "It uses cookies", "https://policies.google.com/technologies/partner-sites",
                 "https://tools.google.com/dlpage/gaoptout", "Google Fonts", "Do Not Track"):
        assert must in p, must
