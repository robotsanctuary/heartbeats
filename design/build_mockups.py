"""
design/build_mockups.py

Renders three throwaway design directions for the public site from the
REAL local data (at-risk animals, their photos and deadlines), so the
look can be judged on actual content instead of placeholders.

Output (contains animal photos, so it lives with the data, not in git):
    $MOCKUP_DIR (default /Volumes/Extreme/heartbeats-data/mockups)/
        A-gentle.html  B-urgent.html  C-photo.html

Each file is self-contained (photos embedded), mobile-first.
Copy marked [draft] is placeholder, not final wording.

Usage:
    ../heartbeats-venv/bin/python design/build_mockups.py
"""

import base64
import html
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402

TZ = ZoneInfo("America/Chicago")
OUT = Path(os.environ.get("MOCKUP_DIR") or "/Volumes/Extreme/heartbeats-data/mockups")
LIMIT = 14


def load(today: date):
    with db.session() as c:
        rows = c.execute(
            """SELECT * FROM pets WHERE status='AT_RISK' AND deadline_timestamp IS NOT NULL
               ORDER BY deadline_timestamp, pet_id LIMIT ?""", (LIMIT,)).fetchall()
        totals = c.execute(
            "SELECT count(*) n, sum(deadline_timestamp IS NOT NULL) d FROM pets WHERE status='AT_RISK'").fetchone()
    pets = []
    for r in rows:
        d = db.parse_ts(r["deadline_timestamp"]).astimezone(TZ).date()
        days = (d - today).days
        img = ""
        if r["local_image_path"] and Path(r["local_image_path"]).exists():
            img = "data:image/jpeg;base64," + base64.b64encode(Path(r["local_image_path"]).read_bytes()).decode()
        desc = r["description"] or ""
        blurb = desc if len(desc) <= 170 else desc[:170].rsplit(" ", 1)[0].rstrip(",;:") + "…"
        pets.append({
            "id": r["pet_id"], "name": (r["name"] or "No name yet").title(),
            "species": r["species"].lower(), "breed": r["breed"] or "Unknown breed",
            "age": _age(r["age"]), "sex": (r["sex"] or "").lower(),
            "deadline": d, "days": days, "img": img, "blurb": blurb,
        })
    return pets, totals


def _age(a):
    if not a:
        return ""
    a = a.lower().replace("years", "yr").replace("year", "yr").replace("months", "mo").replace("month", "mo")
    return a.replace("weeks", "wk").replace("week", "wk")


def when(p, short=False):
    d = p["days"]
    if d < 0:
        return "Deadline passed" if short else f"Deadline passed ({p['deadline']:%b %-d}), still listed"
    if d == 0:
        return "Today"
    if d == 1:
        return "Tomorrow"
    return f"{p['deadline']:%a %b %-d}" if not short else f"In {d} days"


def group(pets):
    groups = {}
    for p in pets:
        key = "past" if p["days"] < 0 else ("today" if p["days"] == 0 else ("tomorrow" if p["days"] == 1 else f"{p['deadline']:%A, %b %-d}"))
        groups.setdefault(key, []).append(p)
    return groups


def e(s):
    return html.escape(str(s))


def page(title, fonts, css, body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?{fonts}&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0}}img{{display:block;max-width:100%}}a{{color:inherit;text-decoration:none}}
{css}</style></head><body>{body}</body></html>"""


# ---------------------------------------------------------------- A: gentle

def gentle(pets, totals, today):
    css = """
:root{--paper:oklch(97.5% 0.012 75);--ink:oklch(25% 0.02 50);--muted:oklch(50% 0.02 55);--line:oklch(89% 0.015 70);--accent:oklch(52% 0.11 35);--soft:oklch(93% 0.03 50)}
body{background:var(--paper);color:var(--ink);font:16px/1.5 "Source Sans 3",system-ui,sans-serif}
header{padding:28px 22px 18px}
.brand{font:600 15px/1 "Fraunces",serif;letter-spacing:.02em;color:var(--accent)}
h1{font:400 34px/1.08 "Fraunces",serif;margin:18px 0 10px;letter-spacing:-.01em}
.lede{color:var(--muted);font-size:16px;max-width:30ch}
.where{margin-top:14px;font-size:14px;color:var(--muted)}
.where b{color:var(--ink);font-weight:600}
section{padding:6px 22px 4px}
h2{font:500 13px/1 "Source Sans 3";text-transform:uppercase;letter-spacing:.12em;color:var(--muted);padding:22px 0 12px;border-top:1px solid var(--line)}
h2.now{color:var(--accent)}
.pet{display:grid;grid-template-columns:104px 1fr;gap:14px;padding:12px 0 18px}
.pet img{width:104px;height:104px;object-fit:cover;border-radius:52px}
.name{font:500 22px/1.15 "Fraunces",serif}
.meta{font-size:14px;color:var(--muted);margin:2px 0 6px}
.blurb{font-size:14.5px;line-height:1.45;color:oklch(35% 0.02 50)}
.help{display:inline-block;margin-top:10px;padding:9px 16px;border-radius:999px;background:var(--soft);color:var(--accent);font-weight:600;font-size:14px;text-decoration:none;min-height:40px}
.note{font-size:12px;color:var(--muted);padding:24px 22px 40px}
"""
    g = group(pets)
    sec = []
    for key, items in g.items():
        label = {"past": "Past their date, still listed", "today": "Today", "tomorrow": "Tomorrow"}.get(key, key)
        rows = "".join(f"""<article class="pet"><img src="{p['img']}" alt="Photo of {e(p['name'])}">
<div><div class="name">{e(p['name'])}</div><div class="meta">{e(p['age'])} · {e(p['breed'])}</div>
<p class="blurb">{e(p['blurb'])}</p><a class="help" href="#">Foster or adopt {e(p['name'])}</a></div></article>""" for p in items)
        sec.append(f'<section><h2 class="{"now" if key in ("today","past") else ""}">{e(label)}</h2>{rows}</section>')
    body = f"""<header><div class="brand">Heartbeats</div>
<h1>They're running out of time. You might be their way out.</h1>
<p class="lede">Dogs and cats at Dallas Animal Services with a scheduled date. [draft]</p>
<p class="where"><b>{totals['n']}</b> animals need placement · <b>{totals['d']}</b> have a date</p></header>
{''.join(sec)}<p class="note">Mockup A · Gentle · real data from {today:%b %-d}. Photos and details from Dallas Animal Services.</p>"""
    return page("Heartbeats — A gentle", "family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Source+Sans+3:wght@400;600", css, body)


# ---------------------------------------------------------------- B: urgent

def urgent(pets, totals, today):
    css = """
:root{--bg:#fff;--ink:oklch(18% 0.01 260);--muted:oklch(48% 0.01 260);--line:oklch(90% 0.005 260);--red:oklch(55% 0.21 27);--amber:oklch(62% 0.15 65)}
body{background:var(--bg);color:var(--ink);font:15px/1.45 "IBM Plex Sans",system-ui,sans-serif}
.bar{position:sticky;top:0;z-index:2;background:var(--ink);color:#fff;padding:12px 16px;display:flex;justify-content:space-between;align-items:baseline}
.bar b{font:700 17px/1 "Archivo Narrow",sans-serif;letter-spacing:.04em;text-transform:uppercase}
.bar span{font-size:13px;opacity:.8}
.counts{display:grid;grid-template-columns:repeat(3,1fr);border-bottom:1px solid var(--line)}
.counts div{padding:14px 16px;border-right:1px solid var(--line)}
.counts div:last-child{border:0}
.counts strong{display:block;font:700 26px/1 "Archivo Narrow",sans-serif}
.counts .r strong{color:var(--red)}
.counts small{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
h2{font:700 13px/1 "Archivo Narrow",sans-serif;text-transform:uppercase;letter-spacing:.1em;padding:18px 16px 8px;color:var(--muted)}
h2.r{color:var(--red)}
.row{display:grid;grid-template-columns:76px 1fr auto;gap:12px;align-items:center;padding:10px 16px;border-top:1px solid var(--line)}
.row img{width:76px;height:76px;object-fit:cover}
.n{font:700 19px/1.1 "Archivo Narrow",sans-serif;text-transform:uppercase;letter-spacing:.02em}
.m{font-size:13px;color:var(--muted)}
.id{font:12px "IBM Plex Mono",monospace;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row>div{min-width:0}
.tag{font:700 12px/1 "Archivo Narrow",sans-serif;text-transform:uppercase;letter-spacing:.06em;padding:7px 9px;border:1.5px solid currentColor;white-space:nowrap}
.tag.today,.tag.past{background:var(--red);border-color:var(--red);color:#fff}
.tag.tomorrow{color:var(--red)}
.tag.later{color:var(--amber)}
.cta{display:block;margin:20px 16px;padding:15px;text-align:center;background:var(--red);color:#fff;font:700 16px/1 "Archivo Narrow",sans-serif;text-transform:uppercase;letter-spacing:.06em;text-decoration:none}
.note{font-size:12px;color:var(--muted);padding:0 16px 40px}
"""
    n_today = sum(1 for p in pets if p["days"] <= 0)
    n_tom = sum(1 for p in pets if p["days"] == 1)
    rows = []
    for key, items in group(pets).items():
        label = {"past": "Past deadline · still listed", "today": "Deadline today", "tomorrow": "Deadline tomorrow"}.get(key, key)
        rows.append(f'<h2 class="{"r" if key in ("today","past","tomorrow") else ""}">{e(label)}</h2>')
        for p in items:
            cls = "past" if p["days"] < 0 else "today" if p["days"] == 0 else "tomorrow" if p["days"] == 1 else "later"
            tag = {"past": "Overdue", "today": "Today", "tomorrow": "Tomorrow"}.get(cls, f"{p['days']} days")
            rows.append(f"""<a class="row" href="#"><img src="{p['img']}" alt=""><div><div class="n">{e(p['name'])}</div>
<div class="m">{e(p['age'])} · {e(p['breed'])}</div><div class="id">{e(p['id'])} · Dallas</div></div>
<span class="tag {cls}">{tag}</span></a>""")
    body = f"""<div class="bar"><b>Heartbeats</b><span>Dallas · updated 3pm</span></div>
<div class="counts"><div class="r"><strong>{n_today}</strong><small>Today</small></div>
<div><strong>{n_tom}</strong><small>Tomorrow</small></div><div><strong>{totals['n']}</strong><small>Listed</small></div></div>
{''.join(rows)}<a class="cta" href="#">How to pull a dog today [draft]</a>
<p class="note">Mockup B · Urgent · real data from {today:%b %-d}.</p>"""
    return page("Heartbeats — B urgent", "family=Archivo+Narrow:wght@700&family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono", css, body)


# ---------------------------------------------------------------- C: photo-first

def photo(pets, totals, today):
    css = """
:root{--bg:oklch(16% 0.01 60);--ink:oklch(97% 0.01 80);--muted:oklch(72% 0.015 70);--accent:oklch(78% 0.14 75);--red:oklch(66% 0.19 28)}
body{background:var(--bg);color:var(--ink);font:15px/1.45 "Manrope",system-ui,sans-serif}
header{padding:22px 16px 14px;display:flex;justify-content:space-between;align-items:end}
.brand{font:400 30px/1 "Instrument Serif",serif}
.brand i{color:var(--accent)}
header p{font-size:13px;color:var(--muted);text-align:right}
.filters{display:flex;gap:8px;padding:4px 16px 14px;overflow:hidden}
.chip{padding:8px 14px;border-radius:999px;border:1px solid oklch(35% 0.01 60);font-size:13px;white-space:nowrap;min-height:36px}
.chip.on{background:var(--ink);color:var(--bg);border-color:var(--ink);font-weight:700}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:3px}
.tile{position:relative;aspect-ratio:3/4;overflow:hidden}
.tile img{width:100%;height:100%;object-fit:cover;object-position:50% 30%}
.tile.big{grid-column:span 2;aspect-ratio:4/3}
.cap{position:absolute;inset:auto 0 0 0;padding:40px 10px 10px;background:linear-gradient(transparent,oklch(8% 0 0 / .92))}
.cap b{font:400 24px/1 "Instrument Serif",serif;display:block}
.tile.big .cap b{font-size:34px}
.cap small{font-size:12px;color:var(--muted)}
.when{position:absolute;top:8px;left:8px;font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;padding:5px 8px;background:var(--ink);color:var(--bg)}
.when.hot{background:var(--red);color:#fff}
.note{font-size:12px;color:var(--muted);padding:18px 16px 40px}
"""
    tiles = []
    for i, p in enumerate(pets):
        hot = p["days"] <= 1
        tiles.append(f"""<a class="tile{' big' if i == 0 else ''}" href="#"><img src="{p['img']}" alt="Photo of {e(p['name'])}">
<span class="when{' hot' if hot else ''}">{e(when(p, short=True))}</span>
<div class="cap"><b>{e(p['name'])}</b><small>{e(p['age'])} · {e(p['breed'].split(' / ')[0])}</small></div></a>""")
    body = f"""<header><div class="brand">Heart<i>beats</i></div><p>{totals['n']} in Dallas<br>need a way out</p></header>
<div class="filters"><span class="chip on">Soonest</span><span class="chip">Dogs</span><span class="chip">Cats</span><span class="chip">Seniors</span><span class="chip">Small</span></div>
<div class="grid">{''.join(tiles)}</div><p class="note">Mockup C · Photo-first · real data from {today:%b %-d}. Filters are non-working placeholders.</p>"""
    return page("Heartbeats — C photo", "family=Instrument+Serif&family=Manrope:wght@400;700;800", css, body)


if __name__ == "__main__":
    today = datetime.now(TZ).date()
    pets, totals = load(today)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in [("A-gentle", gentle), ("B-urgent", urgent), ("C-photo", photo)]:
        (OUT / f"{name}.html").write_text(fn(pets, totals, today))
        print(OUT / f"{name}.html")
