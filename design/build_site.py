"""
design/build_site.py

Static PREVIEW of the public site (direction A "Gentle", chosen
2026-10-19), rendered from the real local DB. Not published anywhere:
hosting is still undecided. Output lives with the data, not in git,
because it contains animal photos.

Pages:
    index.html               at-risk list, grouped by deadline day, plus
                             "needs a foster now" (no fixed date, e.g. neonates)
    animals/<pet_id>.html    one animal: big photo, facts, full description,
                             "Foster or adopt" -> that animal's page AT ITS SHELTER
    help.html                about / how to help
    remembered.html          memorial: only status EUTHANIZED, which only a
                             human ever sets (see schema.sql)

Usage:
    ../heartbeats-venv/bin/python design/build_site.py
    SITE_PREVIEW_DIR=/some/dir ../heartbeats-venv/bin/python design/build_site.py
"""

import html
from urllib.parse import quote
import os
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
from shelters.registry import adopt_url, shelter_info, shelter_path, shelters_by_state, SHELTERS  # noqa: E402

SITE_NAME = "Fading Heartbeats"
TAGLINE = "Every heartbeat deserves a home."
DOMAIN = "fadingheartbeats.com"
# Absolute base for share links + link previews. Pages swap in their real address at view time,
# so the LAN preview still shares working links.
# Launch switches. Remembered (memorial) stays hidden until it's announced: no tab, no page,
# no pages for those animals. The shelter menu + shelter line on cards appear once 2+ shelters exist.
SHOW_REMEMBERED = os.environ.get("SHOW_REMEMBERED") == "1"
SHOW_PICKER = None  # None = automatic (2+ registered shelters); set by build()
SITE_URL = (os.environ.get("SITE_URL") or f"https://{DOMAIN}").rstrip("/")
DEFAULT_TZ = ZoneInfo("America/Chicago")
OUT = Path(os.environ.get("SITE_PREVIEW_DIR") or "/Volumes/Extreme/heartbeats-data/site-preview")


def e(s) -> str:
    return html.escape("" if s is None else str(s))


# ------------------------------------------------------------------ data

def _age(a):
    if not a:
        return ""
    a = a.lower()
    for long, short in (("years", "yrs"), ("year", "yr"), ("months", "mo"), ("month", "mo"),
                        ("weeks", "wks"), ("week", "wk")):
        a = a.replace(long, short)
    return a


def _sex(s):
    s = (s or "").lower()
    return {"neutered": "Male, neutered", "spayed": "Female, spayed"}.get(s, s.capitalize())


def to_view(r, today: date) -> dict:
    info = shelter_info(r["shelter_name"]) or {}
    tz = ZoneInfo(info.get("timezone", "America/Chicago"))
    deadline = db.parse_ts(r["deadline_timestamp"]).astimezone(tz).date() if r["deadline_timestamp"] else None
    gone = db.parse_ts(r["euthanized_at"]).astimezone(tz).date() if r.get("euthanized_at") else None
    img = Path(r["local_image_path"]) if r["local_image_path"] else None
    return {
        "id": r["pet_id"],
        "name": (r["name"] or "No name yet").title(),
        "species": r["species"],
        "breed": r["breed"] or "Mixed / unknown breed",
        "age": _age(r["age"]),
        "sex": _sex(r["sex"]),
        "shelter": info.get("short_name", r["shelter_name"]),
        "city": f"{info['city']}, {info['state']}" if info.get("city") else "",
        "path": shelter_path(r["shelter_name"]),
        "raw_shelter": r["shelter_name"],
        "contact": info.get("contact_email"),
        "adopt": adopt_url(r["shelter_name"], r["pet_id"]),
        "deadline": deadline,
        "days": (deadline - today).days if deadline else None,
        "gone": gone,
        "img": img if img and img.exists() else None,
        "desc": r["description"] or "",
    }


def load(today: date):
    with db.session() as c:
        at_risk = c.execute(
            """SELECT * FROM pets WHERE status='AT_RISK'
               ORDER BY deadline_timestamp IS NULL, deadline_timestamp, name, pet_id""").fetchall()
        remembered = c.execute(
            """SELECT * FROM pets WHERE status='EUTHANIZED'
               ORDER BY euthanized_at DESC, pet_id""").fetchall()
        saved = c.execute(
            "SELECT count(*) n FROM pets WHERE status IN ('ADOPTED','SAFE','TRANSFERRED')").fetchone()["n"]
    return ([to_view(r, today) for r in at_risk],
            [to_view(r, today) for r in remembered],
            saved)


# ------------------------------------------------------------------ chrome

CSS = """
*{box-sizing:border-box;margin:0;padding:0}img{display:block;max-width:100%}a{color:inherit}
:root{--paper:oklch(97.5% 0.012 75);--ink:oklch(25% 0.02 50);--muted:oklch(50% 0.02 55);--line:oklch(89% 0.015 70);
--accent:oklch(52% 0.11 35);--soft:oklch(93% 0.03 50);--quiet:oklch(94% 0.008 75)}
body{background:var(--paper);color:var(--ink);font:16px/1.55 "Source Sans 3",system-ui,sans-serif;-webkit-text-size-adjust:100%}
.wrap{max-width:640px;margin:0 auto}
nav{margin:0 22px;padding:14px 0 0;border-bottom:1px solid var(--line)}
.brand{font:600 17px/1 "Fraunces",serif;color:var(--accent);text-decoration:none;display:flex;gap:7px;align-items:center}
.brand svg{width:16px;height:16px}
nav .links{display:flex;gap:20px;font-size:15px;margin-top:6px}
nav .links a{text-decoration:none;color:var(--muted);padding:10px 0 12px;white-space:nowrap;border-bottom:2px solid transparent}
nav .links a.on{color:var(--ink);font-weight:600;border-color:var(--accent)}
header{padding:30px 22px 18px}
h1{font:400 36px/1.08 "Fraunces",serif;letter-spacing:-.01em;margin-bottom:12px}
.lede{color:var(--muted);max-width:56ch}
.stats{margin-top:16px;font-size:14px;color:var(--muted)}.stats b{color:var(--ink);font-weight:600}
section{padding:4px 22px}
h2{font:500 13px/1 "Source Sans 3";text-transform:uppercase;letter-spacing:.12em;color:var(--muted);padding:24px 0 12px;border-top:1px solid var(--line)}
h2.now{color:var(--accent)}
.pet{display:grid;grid-template-columns:96px 1fr;gap:14px;padding:12px 0 18px;text-decoration:none}
.pet img,.pet .noimg{width:96px;height:96px;object-fit:cover;object-position:50% 25%;border-radius:50%;background:var(--soft)}
.name{font:500 22px/1.15 "Fraunces",serif}
.meta{font-size:14px;color:var(--muted);margin:2px 0 6px}
.blurb{font-size:14.5px;line-height:1.45;color:oklch(35% 0.02 50)}
.more{display:inline-block;margin-top:8px;font-size:14px;font-weight:600;color:var(--accent)}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:12px 22px;border-radius:999px;
background:var(--accent);color:#fff;font-weight:600;font-size:16px;text-decoration:none;width:100%}
.btn.soft{background:var(--soft);color:var(--accent)}
.hero{width:100%;aspect-ratio:1/1;object-fit:cover;background:var(--soft)}
.detail{padding:20px 22px}
.detail h1{margin:6px 0 4px}
.when{display:inline-block;font-size:13px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--accent)}
.facts{display:grid;grid-template-columns:auto 1fr;gap:6px 16px;margin:18px 0;padding:16px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);font-size:15px}
.facts dt{color:var(--muted)}
.story p{margin-bottom:12px}
.actions{display:grid;gap:10px;margin:22px 0 8px}
.small{font-size:13px;color:var(--muted)}
.prose{padding:8px 22px 10px}.prose h2{margin-top:10px}
.prose p,.prose li{margin-bottom:10px}.prose ol{padding-left:20px}
.prose strong{font-weight:600}
.mem{display:grid;grid-template-columns:repeat(2,1fr);gap:22px 16px;padding:8px 0 20px}
.mem figure{text-align:center}
.mem img,.mem .noimg{width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:50%;filter:grayscale(.35) sepia(.15);background:var(--quiet)}
.mem figcaption{margin-top:8px;font:500 19px/1.2 "Fraunces",serif}
.mem small{display:block;font:13px/1.4 "Source Sans 3";color:var(--muted)}
.empty{padding:22px;background:var(--quiet);border-radius:14px;color:var(--muted);margin:10px 0 24px}
footer{margin:24px 22px 0;padding:28px 0 44px;font-size:12.5px;color:var(--muted);border-top:1px solid var(--line)}
.draft{color:oklch(55% 0.12 300);font-size:.8em}
.picker{margin-top:18px;display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px}
.picker label{font-size:13px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.picker select{font:600 16px "Source Sans 3",system-ui,sans-serif;color:var(--ink);background:#fff;border:1px solid var(--line);
border-radius:12px;min-height:44px;padding:8px 36px 8px 12px;width:100%;max-width:420px;appearance:none;
background-image:linear-gradient(45deg,transparent 50%,currentColor 50%),linear-gradient(135deg,currentColor 50%,transparent 50%);
background-position:calc(100% - 18px) 50%,calc(100% - 13px) 50%;background-size:5px 5px;background-repeat:no-repeat}
.where{font-size:13px;color:var(--muted);margin-top:-4px;margin-bottom:6px}
.crumb{font-size:14px;margin-bottom:10px}.crumb a{color:var(--accent);font-weight:600;text-decoration:none}
.shelterlist li{margin-bottom:6px}.shelterlist a{color:var(--accent);font-weight:600}
.share{margin:18px 0 6px}.share .lbl{font-size:13px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:8px}
.chips{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.chip{display:flex;align-items:center;justify-content:center;gap:6px;min-height:44px;padding:8px 6px;border-radius:12px;border:1px solid var(--line);
background:#fff;color:var(--ink);font:600 14px/1.1 "Source Sans 3",system-ui,sans-serif;text-decoration:none;cursor:pointer}
.chip svg{width:17px;height:17px;flex:none;color:var(--accent)}.chip.more{display:none}
.dwrap{padding-top:14px}
@media (min-width:900px){
.wrap.wide{max-width:1080px}
h1{font-size:44px}
.pets{display:grid;grid-template-columns:1fr 1fr;gap:0 44px}
.mem{grid-template-columns:repeat(4,1fr);gap:28px 24px}
.dwrap{display:grid;grid-template-columns:minmax(0,11fr) minmax(0,10fr);gap:44px;align-items:start;padding:32px 22px 0}
.dwrap .hero{border-radius:20px;position:sticky;top:24px}
.dwrap .detail{padding:0}
.dwrap .actions{max-width:420px}
}
"""

HEART = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 21s-7.5-4.6-9.6-9.2C.8 8.3 3 4.5 6.7 4.5'
         'c2.1 0 3.6 1.1 4.3 2.4h2c.7-1.3 2.2-2.4 4.3-2.4 3.7 0 5.9 3.8 4.3 7.3C19.5 16.4 12 21 12 21z"/></svg>')


def page(title, body, active, root="", wide=False, meta=""):
    links = [("index.html", "Animals", "list"), ("help.html", "How to help", "help")]
    if SHOW_REMEMBERED:
        links.append(("remembered.html", "Remembered", "mem"))
    nav = "".join(f'<a href="{root}{h}" class="{"on" if k == active else ""}">{t}</a>' for h, t, k in links)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>{meta or f'<meta name="description" content="{e(TAGLINE)}">'}
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Source+Sans+3:wght@400;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap{" wide" if wide else ""}">
<nav><a class="brand" href="{root}index.html">{HEART}{e(SITE_NAME)}</a><div class="links">{nav}</div></nav>
{body}
<footer>{e(SITE_NAME)} · {e(DOMAIN)}<br>We are not a shelter. Every animal's details and photo come from the shelter that has them;
please contact that shelter directly. Information can be out of date by a few hours. <span class="draft">[draft]</span></footer>
</div></body></html>"""


def photo(p, root, cls=""):
    if p["img"]:
        return f'<img class="{cls}" src="{root}img/{e(p["img"].name)}" alt="Photo of {e(p["name"])}" loading="lazy">'
    return f'<div class="noimg {cls}" role="img" aria-label="No photo yet"></div>'


def when(p):
    d = p["days"]
    if d is None:
        return "Needs a foster now"
    if d < 0:
        return f"Date passed ({p['deadline']:%b %-d}), still listed"
    if d == 0:
        return "Today"
    if d == 1:
        return "Tomorrow"
    return f"By {p['deadline']:%A, %b %-d}"


def blurb(text, n=150):
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0].rstrip(",;:.!?") + "…"


# ------------------------------------------------------------------ sharing

ICONS = {
    "sms": '<path d="M4 5h16v11H8l-4 4z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
    "mail": '<path d="M3 6h18v12H3zM3 7l9 6 9-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
    "fb": '<path fill="currentColor" d="M14 8h3V4h-3c-2.8 0-4 1.8-4 4.3V10H7v4h3v7h4v-7h3l.5-4H14V8.6c0-.4.2-.6.6-.6z"/>',
    "x": '<path fill="currentColor" d="M17.8 3h3.1l-6.8 7.8 8 10.2h-6.3l-4.9-6.4L5.3 21H2.2l7.3-8.3L1.8 3h6.4l4.4 5.9zm-1.1 16.2h1.7L7.4 4.7H5.6z"/>',
    "wa": '<path fill="currentColor" d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm5.3 14c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .2-3.3-.7-2.8-1.1-4.5-4-4.7-4.2-.1-.2-1.1-1.5-1.1-2.8s.7-2 1-2.3c.2-.3.5-.3.7-.3h.5c.2 0 .4 0 .6.5l.8 2c.1.2.1.3 0 .5l-.4.6c-.1.2-.3.3-.1.6.2.3.8 1.3 1.6 2 1.1 1 2 1.3 2.3 1.4.3.2.4.1.6-.1l.8-1c.2-.2.4-.2.6-.1l1.9.9c.3.1.4.2.5.3.1.2.1.8-.1 1.5z"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "more": '<path d="M12 3v12M7 8l5-5 5 5M5 13v7h14v-7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
}


def share_text(p) -> str:
    """One short, specific ask. Used for SMS, email, X, WhatsApp and the phone share sheet."""
    where = f" at {p['shelter']}" + (f" in {p['city'].split(',')[0]}" if p.get("city") else "")
    d = p["days"]
    if d is None:
        need = f"{p['name']} needs a foster home now{where}."
    elif d < 0:
        need = f"{p['name']} is past their shelter date and still waiting{where}."
    elif d == 0:
        need = f"{p['name']} needs a way out of the shelter today{where}."
    elif d == 1:
        need = f"{p['name']} needs a way out of the shelter by tomorrow{where}."
    else:
        need = f"{p['name']} needs a way out of the shelter by {p['deadline']:%A, %b %-d}{where}."
    return need + " Can you foster, adopt, or share?"


def animal_url(p) -> str:
    return f"{SITE_URL}/animals/{quote(p['id'])}.html"


def share_links(p) -> list:
    """(key, label, href). Hrefs embed the canonical URL; share_js swaps in the page's real address."""
    url, text = animal_url(p), share_text(p)
    u, t, both = quote(url, safe=""), quote(text, safe=""), quote(f"{text} {url}", safe="")
    subj = quote(f"Can you help {p['name']}?", safe="")
    return [
        ("sms", "Text", f"sms:?&body={both}"),
        ("mail", "Email", f"mailto:?subject={subj}&body={quote(text + chr(10) + chr(10) + url, safe='')}"),
        ("fb", "Facebook", f"https://www.facebook.com/sharer/sharer.php?u={u}"),
        ("x", "X", f"https://twitter.com/intent/tweet?text={t}&url={u}"),
        ("wa", "WhatsApp", f"https://wa.me/?text={both}"),
    ]


def share_block(p, label) -> str:
    newtab = ' target="_blank" rel="noopener"'
    chips = "".join(
        f'<a class="chip" href="{e(h)}"{"" if k in ("sms", "mail") else newtab}>'
        f'<svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[k]}</svg>{e(n)}</a>' for k, n, h in share_links(p))
    chips += (f'<button type="button" class="chip copy"><svg viewBox="0 0 24 24" aria-hidden="true">{ICONS["link"]}</svg>Copy link</button>'
              f'<button type="button" class="chip more"><svg viewBox="0 0 24 24" aria-hidden="true">{ICONS["more"]}</svg>More…</button>')
    return f'<div class="share"><div class="lbl">{e(label)}</div><div class="chips">{chips}</div></div>'


def share_js(p) -> str:
    canon = animal_url(p)
    data = {"canon": canon, "text": share_text(p), "title": f"Can you help {p['name']}?"}
    import json
    return ("<script>(()=>{const d=" + json.dumps(data).replace("</", "<\\/") + r""";
const here=location.href.split('#')[0];
if(here!==d.canon)document.querySelectorAll('.share a.chip').forEach(a=>{a.href=a.href.split(encodeURIComponent(d.canon)).join(encodeURIComponent(here))});
document.querySelectorAll('.share .copy').forEach(b=>b.onclick=()=>{const done=()=>{const t=b.lastChild.textContent;b.lastChild.textContent='Copied';setTimeout(()=>b.lastChild.textContent=t,1800)};
if(navigator.clipboard&&isSecureContext)navigator.clipboard.writeText(here).then(done);else{const i=document.createElement('textarea');i.value=here;document.body.appendChild(i);i.select();document.execCommand('copy');i.remove();done()}});
if(navigator.share)document.querySelectorAll('.share .more').forEach(b=>{b.style.display='flex';b.onclick=()=>navigator.share({title:d.title,text:d.text,url:here}).catch(()=>{})});
})()</script>""")


def share_meta(p) -> str:
    """Link previews (iMessage, Facebook, X, WhatsApp, Slack): photo + name instead of a bare link."""
    img = f"{SITE_URL}/img/{quote(p['img'].name)}" if p["img"] else ""
    desc = share_text(p)
    tags = [("description", desc, "name"), ("og:type", "article", "property"), ("og:site_name", SITE_NAME, "property"),
            ("og:title", f"Can you help {p['name']}?", "property"), ("og:description", desc, "property"),
            ("og:url", animal_url(p), "property"), ("twitter:card", "summary_large_image" if img else "summary", "name")]
    if img:
        tags += [("og:image", img, "property"), ("og:image:alt", f"Photo of {p['name']}", "property")]
    return "".join(f'<meta {attr}="{e(k)}" content="{e(v)}">' for k, v, attr in tags) + f'<link rel="canonical" href="{e(animal_url(p))}">'


# ------------------------------------------------------------------ pages

def pet_sections(pets, root="", show_shelter=True):
    """Animals grouped by deadline day: past, today, tomorrow, later days, then no-date last."""
    groups: dict = {}
    for p in pets:
        d = p["days"]
        key = ("nodate" if d is None else "past" if d < 0 else "today" if d == 0
               else "tomorrow" if d == 1 else f"{p['deadline']:%A, %b %-d}")
        groups.setdefault(key, []).append(p)
    order = ["past", "today", "tomorrow"]
    keys = [k for k in order if k in groups] + [k for k in groups if k not in order + ["nodate"]]
    keys += ["nodate"] if "nodate" in groups else []
    labels = {"past": "Past their date, still listed", "today": "Today", "tomorrow": "Tomorrow",
              "nodate": "Needs a foster now · no fixed date"}
    secs = []
    for k in keys:
        rows = []
        for p in groups[k]:
            text = blurb(p["desc"]) if p["desc"] else (
                "Too young to stay in the shelter. Needs a foster home." if k == "nodate" else "")
            where = f'<div class="where">{e(p["shelter"])}{" · " + e(p["city"]) if p["city"] else ""}</div>' if show_shelter else ""
            rows.append(f"""<a class="pet" href="{root}animals/{e(p['id'])}.html">{photo(p, root)}
<div><div class="name">{e(p['name'])}</div><div class="meta">{e(p['age'])} · {e(p['breed'])}</div>{where}
<p class="blurb">{e(text)}</p><span class="more">Meet {e(p['name'])} →</span></div></a>""")
        secs.append(f'<section><h2 class="{"now" if k in ("past", "today") else ""}">{e(labels.get(k, k))}</h2><div class="pets">{"".join(rows)}</div></section>')
    return "".join(secs)


def picker(root="", current=None, counts=None):
    """'Choose your shelter' menu, grouped by state. Plain links in <noscript> for no-JS browsers."""
    if not SHOW_PICKER:
        return ""
    counts = counts or {}
    opts = [f'<option value="{root}index.html"{" selected" if current is None else ""}>All shelters</option>']
    plain = []
    for state, items in shelters_by_state():
        o = []
        for name, info in items:
            path = shelter_path(name)
            n = counts.get(name, 0)
            o.append(f'<option value="{root}{path}/index.html"{" selected" if name == current else ""}>'
                     f'{e(info["short_name"] if info["city"].lower() in info["short_name"].lower() else info["city"] + " · " + info["short_name"])} ({n})</option>')
            plain.append(f'<a href="{root}{path}/index.html">{e(info["short_name"])}</a>')
        opts.append(f'<optgroup label="{e(state)}">{"".join(o)}</optgroup>')
    return (f'<div class="picker"><label for="shelter-pick">Choose your shelter</label>'
            f'<select id="shelter-pick" onchange="location.href=this.value">{"".join(opts)}</select>'
            f'<noscript>{" · ".join(plain)}</noscript></div>')


def shelter_counts(pets):
    c: dict = {}
    for p in pets:
        c[p["raw_shelter"]] = c.get(p["raw_shelter"], 0) + 1
    return c


def index_page(pets, saved, today):
    dated = sum(p["days"] is not None for p in pets)
    n_shelters = len({p["shelter"] for p in pets})
    body = f"""<header><h1>{e(TAGLINE)}</h1>
<p class="lede">Dogs and cats at {n_shelters} shelter{"" if n_shelters == 1 else "s"} who are out of time or close to it. Fostering even for two weeks saves a life.</p>
<p class="stats"><b>{len(pets)}</b> need a way out · <b>{dated}</b> have a date · <b>{saved}</b> made it out recently</p>
{picker("", None, shelter_counts(pets))}</header>
{pet_sections(pets, "", show_shelter=bool(SHOW_PICKER))}"""
    return page(f"{SITE_NAME}: {TAGLINE}", body, "list", wide=True)


def shelter_page(name, info, pets, all_pets):
    root = "../../"
    dated = sum(p["days"] is not None for p in pets)
    site = f' · <a href="{e(info["website"])}" rel="noopener" style="white-space:nowrap">Shelter website</a>' if info.get("website") else ""
    listing = pet_sections(pets, root, show_shelter=False) if pets else (
        '<section><div class="empty">No animals from this shelter are on an at-risk list right now. '
        'That can change quickly, so check back.</div></section>')
    body = f"""<header><p class="crumb"><a href="{root}index.html">← All shelters</a></p>
<h1>{e(info["short_name"])}</h1>
<p class="lede">{e(info.get("address") or f"{info['city']}, {info['state']}")}{site}</p>
<p class="stats"><b>{len(pets)}</b> need a way out · <b>{dated}</b> have a date</p>
{picker(root, name, shelter_counts(all_pets))}</header>
{listing}"""
    return page(f"{info['short_name']} · {SITE_NAME}", body, "list", root=root, wide=True)


def detail_page(p):
    facts = [("Age", p["age"]), ("Sex", p["sex"]), ("Breed", p["breed"]),
             ("Shelter", f"{p['shelter']}, {p['city']}" if p["city"] else p["shelter"]), ("Animal ID", p["id"])]
    dl = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in facts if v)
    if p["path"]:
        dl += f'<dt></dt><dd><a href="../{e(p["path"])}/index.html" style="color:var(--accent);font-weight:600">More animals at {e(p["shelter"])} →</a></dd>'
    paras = [x.strip() for x in p["desc"].replace("\r", "").split("\n") if x.strip()] or [
        f"The shelter hasn't written {p['name']}'s story yet. "
        + ("Very young animals like this one can't stay in the shelter and need a foster home right away."
           if p["days"] is None else "The best way to learn more is to ask the shelter directly.")]
    story = "".join(f"<p>{e(x)}</p>" for x in paras)
    if p["adopt"]:
        main = f'<a class="btn" href="{e(p["adopt"])}" rel="noopener">Foster or adopt {e(p["name"])}</a>'
    else:
        main = '<p class="small">No direct link to this shelter yet.</p>'
    mail = (f'<a class="btn soft" href="mailto:{e(p["contact"])}?subject={e(p["id"])}%20{e(p["name"])}">'
            f'Email the shelter about {e(p["name"])}</a>') if p["contact"] else ""
    body = f"""<div class="dwrap">{photo(p, "../", "hero")}
<div class="detail"><span class="when">{e(("Shelter date: " + when(p)) if p["days"] is not None and p["days"] >= 0 else when(p))}</span><h1>{e(p['name'])}</h1>
<div class="actions">{main}</div>
<p class="small">Opens {e(p['name'])}'s page on the shelter's own site. Mention ID {e(p['id'])} when you contact them.</p>
{share_block(p, f"Share {p['name']}")}
<dl class="facts">{dl}</dl><div class="story">{story}</div>
<div class="actions">{mail}</div>
{share_block(p, f"Can't take {p['name']} home? Sharing helps too")}</div></div>{share_js(p)}"""
    return page(f"{p['name']} · {SITE_NAME}", body, "list", root="../", wide=True, meta=share_meta(p))


def help_page():
    body = f"""<header><h1>How you can help</h1>
<p class="lede">You don't need a big house or a lot of money. Most of these take one afternoon. <span class="draft">[draft]</span></p></header>
<div class="prose">
<h2>Foster</h2>
<p>Fostering means taking an animal home for a while, often two to four weeks. The shelter usually pays for food and vet care. It frees a kennel and is often the difference between a date and a future.</p>
<h2>Adopt</h2>
<p>If one of these animals is yours, tap <strong>Foster or adopt</strong> on their page. It opens that animal's page at the shelter that has them, with the shelter's own steps.</p>
<h2>Pull as a rescue</h2>
<p>Registered rescue groups can pull animals directly. Contact the shelter's rescue coordinator with the animal ID.</p>
<h2>Share</h2>
<p>Many animals are saved by someone who saw a post from a friend. Every animal has its own page you can share.</p>
<h2>How this site works</h2>
<ol><li>Several times a day we read the public at-risk lists that shelters publish.</li>
<li>Animals with a scheduled date are shown first, soonest on top.</li>
<li>When an animal leaves the list we keep checking, and we never assume the worst. {"An animal only appears under <em>Remembered</em> after a person has confirmed it." if SHOW_REMEMBERED else "We never mark an animal as lost unless a person has confirmed it."}</li></ol>
<p>We are volunteers, not a shelter, and we don't handle adoptions. The shelter always has the final, current answer.</p>
<h2>Shelters we follow</h2>
""" + "".join(f'<p><strong>{e(st)}</strong></p><ul class="shelterlist" style="list-style:none;margin-bottom:12px">'
              + "".join(f'<li><a href="{shelter_path(n)}/index.html">{e(i["short_name"])}</a> · {e(i["city"])}</li>' for n, i in items)
              + "</ul>" for st, items in shelters_by_state()) + """<p>More soon.</p>
</div>"""
    return page(f"How to help · {SITE_NAME}", body, "help")


def remembered_page(gone):
    if gone:
        figs = "".join(f"""<figure>{photo(p, "")}<figcaption>{e(p['name'])}
<small>{e(p['age'])} · {e(p['shelter'])}{f" · {p['gone']:%b %-d, %Y}" if p['gone'] else ""}</small></figcaption></figure>""" for p in gone)
        grid = f'<div class="mem">{figs}</div>'
    else:
        grid = ('<div class="empty">No one is listed here yet. Names only appear after a person has confirmed '
                'what happened. We never guess from an animal leaving a list.</div>')
    body = f"""<header><h1>Remembered</h1>
<p class="lede">For the ones who ran out of time. They were here, they had names, and they mattered. <span class="draft">[draft]</span></p></header>
<section>{grid}</section>"""
    return page(f"Remembered · {SITE_NAME}", body, "mem", wide=True)


# ------------------------------------------------------------------ build

def build(out: Path = OUT, today: date = None, show_remembered: bool = None, show_picker: bool = None):
    global SHOW_REMEMBERED, SHOW_PICKER
    if show_remembered is not None:
        SHOW_REMEMBERED = show_remembered
    SHOW_PICKER = (len(SHELTERS) > 1) if show_picker is None else show_picker
    today = today or datetime.now(DEFAULT_TZ).date()
    pets, gone, saved = load(today)
    tmp = out.with_name(out.name + ".building")
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "animals").mkdir(parents=True)
    (tmp / "img").mkdir()
    if not SHOW_REMEMBERED:
        gone = []
    for p in pets + gone:
        if p["img"]:
            shutil.copy2(p["img"], tmp / "img" / p["img"].name)
        (tmp / "animals" / f"{p['id']}.html").write_text(detail_page(p))
    (tmp / "index.html").write_text(index_page(pets, saved, today))
    for name, info in SHELTERS.items():
        d = tmp / shelter_path(name)
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(shelter_page(name, info, [p for p in pets if p["raw_shelter"] == name], pets))
    (tmp / "help.html").write_text(help_page())
    if SHOW_REMEMBERED:
        (tmp / "remembered.html").write_text(remembered_page(gone))
    if out.exists():
        shutil.rmtree(out)
    tmp.rename(out)
    return {"out": str(out), "at_risk": len(pets), "remembered": len(gone),
            "no_adopt_link": sum(not p["adopt"] for p in pets), "shelter_pages": len(SHELTERS)}


if __name__ == "__main__":
    print(build())
