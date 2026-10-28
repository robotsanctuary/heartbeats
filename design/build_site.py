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
import re
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
# The site dog (and its lab/test pages) ships only once the owner approves it.
SHOW_DOG = os.environ.get("SHOW_DOG") == "1"
# Google Analytics: build() adds it to every .html file it writes, so new or changed pages never need it by hand.
GA_ID = "G-F98F38JQ09"
GA_TAG = f"""<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());

  gtag('config', '{GA_ID}');
</script>
"""
SHOW_PICKER = None  # None = automatic (2+ registered shelters); set by build()
# When this build was made: shown in every footer, and in a meta tag the auto-deploy reads back from the live site.
BUILT = ""        # UTC, e.g. 2026-10-28T02:02:30Z
BUILT_LABEL = ""  # e.g. Oct 27, 9:02 PM CT
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
.brand{font:600 17px/1 "Fraunces",serif;color:var(--accent);text-decoration:none;display:flex;gap:7px;align-items:center}
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
/* ---- modern skin (2026-10-20): brand option 6, Instrument Serif + gradient italic ---- */
:root{--accent:#D9472F;--ink:#1F1A17;--muted:#6B625C;--line:rgba(31,26,23,.09);--soft:#FDEBE4;--paper:#FBF7F3;
--grad:linear-gradient(95deg,#D9472F,#C4304F 55%,#9E2A66);--shadow:0 1px 2px rgba(31,26,23,.04),0 10px 28px -14px rgba(120,60,40,.22)}
body{background:var(--paper);font-family:"Source Sans 3",system-ui,sans-serif}
body::before{content:"";position:fixed;inset:-20%;z-index:-1;pointer-events:none;
background:radial-gradient(38% 32% at 15% 8%,#FFD6C2 0,transparent 70%),radial-gradient(34% 30% at 92% 28%,#FCDDE8 0,transparent 70%),radial-gradient(40% 34% at 45% 100%,#FFE7D6 0,transparent 70%);
animation:drift 30s ease-in-out infinite alternate}
@keyframes drift{to{transform:translate3d(4%,-3%,0) scale(1.07)}}
h1,.name,.brand{font-family:"Instrument Serif",serif;font-weight:400}
h1 i,.brand i{font-style:italic}
.grad{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent;padding-right:.07em;filter:drop-shadow(0 6px 16px rgba(217,71,47,.28))}
header{padding:28px 22px 14px}
h1{font-size:50px;line-height:1;letter-spacing:-.01em;margin-bottom:14px}
.lede{font-size:17.5px;color:var(--muted)}
.stats{font-size:14.5px}
h2{border-top:0;padding:30px 0 14px;display:flex;align-items:center;gap:10px}
h2.now::before{content:"";flex:none;width:8px;height:8px;border-radius:50%;background:var(--accent);animation:ping 1.8s infinite}
@keyframes ping{0%{box-shadow:0 0 0 0 rgba(217,71,47,.55)}70%,100%{box-shadow:0 0 0 10px rgba(217,71,47,0)}}
.pets{display:grid;gap:14px}
.pet{background:#fff;border-radius:22px;padding:14px;gap:16px;border:1px solid rgba(255,255,255,.9);box-shadow:var(--shadow);
transition:transform .3s cubic-bezier(.2,.8,.2,1),box-shadow .3s}
.pet:hover{transform:translateY(-3px);box-shadow:0 2px 4px rgba(31,26,23,.05),0 22px 44px -16px rgba(120,60,40,.32)}
.pet img,.pet .noimg{border-radius:18px;transition:transform .6s cubic-bezier(.2,.8,.2,1)}
.pet:hover img{transform:scale(1.05) rotate(-1deg)}
.name{font-size:30px;line-height:1}
.more{transition:transform .25s}.pet:hover .more{transform:translateX(5px)}
.btn{background:var(--grad);box-shadow:0 12px 26px -12px rgba(196,48,79,.65);transition:transform .15s,box-shadow .25s,filter .2s}
.btn:hover{transform:translateY(-2px);filter:saturate(1.15)}.btn:active{transform:scale(.97)}
.btn.soft{background:#fff;color:var(--accent);border:1px solid var(--line);box-shadow:var(--shadow)}
.dwrap{padding:16px 14px 0}.dwrap .detail{padding:22px 8px}
.hero{border-radius:26px;box-shadow:0 24px 50px -24px rgba(120,60,40,.45)}
.detail h1{font-size:60px;margin:10px 0 6px}
.when{display:inline-flex;align-items:center;gap:8px;background:#fff;border:1px solid var(--line);padding:7px 13px;border-radius:999px;font-size:12px;box-shadow:var(--shadow)}
.when.now::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--accent);animation:ping 1.8s infinite}
.facts{background:#fff;border:1px solid var(--line);border-radius:20px;padding:16px 18px;box-shadow:var(--shadow)}
.chip{border-radius:14px;box-shadow:0 1px 2px rgba(31,26,23,.04);transition:transform .15s,border-color .2s,box-shadow .2s}
.chip:hover{border-color:rgba(217,71,47,.45);transform:translateY(-1px);box-shadow:var(--shadow)}.chip:active{transform:scale(.95)}
.picker select{border-radius:14px;box-shadow:var(--shadow)}
.empty{background:#fff;border:1px solid var(--line)}
.prose h2{padding-top:26px}
footer{border-top:1px solid var(--line)}
/* top bar (header option B, 2026-10-20): full width, logo left, menu right, sticks on scroll */
.topbar{position:sticky;top:0;z-index:30;background:rgba(251,247,243,.8);-webkit-backdrop-filter:blur(16px) saturate(1.4);backdrop-filter:blur(16px) saturate(1.4);border-bottom:1px solid rgba(31,26,23,.08)}
.topbar .in{max-width:1080px;margin:0 auto;padding:10px 22px;display:flex;align-items:center;justify-content:space-between;gap:10px}
.brand{font-size:24px;line-height:1;color:var(--ink);gap:10px;font-weight:400}.brand svg{width:46px;height:auto;overflow:visible}
.topbar .links{display:flex;gap:4px}
.topbar .links a{padding:8px 14px;border-radius:999px;font-size:15px;color:var(--muted);text-decoration:none;white-space:nowrap;transition:color .2s}
.topbar .links a:hover{color:var(--ink)}.topbar .links a.on{background:#fff;color:var(--ink);font-weight:600;box-shadow:var(--shadow)}
@media(max-width:560px){.topbar .in{padding:8px 14px}.brand{font-size:20px;gap:6px}.brand svg{width:32px}.topbar .links a{padding:6px 9px;font-size:13.5px}}
/* home band + "out of time soon" scroller (rebuilt after every scrape, so it changes daily) */
.band{background:linear-gradient(120deg,#FFE3D6,#FCE6EE 60%,#FFF1E6);border-bottom:1px solid var(--line);overflow:hidden}
.band .in{max-width:1080px;margin:0 auto;padding:28px 22px 6px}
.band h1{font-size:42px;margin-bottom:10px}
.pills{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}.pills span{background:#fff;border:1px solid var(--line);border-radius:999px;padding:6px 12px;font-size:14px;color:var(--muted);box-shadow:var(--shadow)}.pills b{color:var(--ink)}
.band .btn{width:auto;margin-top:20px}#list{display:block;scroll-margin-top:70px}
.band .in{display:grid;gap:26px;padding-bottom:34px}
.spot{position:relative;width:100%;max-width:440px;justify-self:center}
.spot .lbl{display:flex;align-items:center;gap:10px;margin-bottom:12px;font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}
.spot .lbl::before{content:"";width:9px;height:9px;border-radius:50%;background:var(--accent);animation:ping 1.8s infinite}
.spot .lbl span{margin-left:auto;font-weight:600;letter-spacing:.04em;color:var(--muted)}
.sq{position:relative;aspect-ratio:1/1}
.sq::before,.sq::after{content:"";position:absolute;inset:0;border-radius:28px;background:#fff;box-shadow:var(--shadow)}
.sq::before{transform:rotate(-4deg) translate(-4px,4px);opacity:.7}.sq::after{transform:rotate(3deg) translate(4px,3px);opacity:.85}
.slide{position:absolute;inset:0;z-index:1;display:block;border-radius:28px;overflow:hidden;border:6px solid #fff;background:var(--soft);
box-shadow:0 30px 50px -24px rgba(120,60,40,.55);text-decoration:none;color:#fff;opacity:0;visibility:hidden;transform:scale(.96) rotate(-1.5deg);
transition:opacity .8s ease,transform .8s cubic-bezier(.2,.8,.2,1),visibility 0s .8s}
.slide.on{opacity:1;visibility:visible;transform:none;transition:opacity .8s ease,transform .8s cubic-bezier(.2,.8,.2,1)}
.slide img,.slide .noimg{width:100%;height:100%;object-fit:cover;object-position:50% 25%}
.slide.on img{animation:kb 9s ease-out forwards}@keyframes kb{from{transform:scale(1.12)}to{transform:scale(1)}}
.slide .cap{position:absolute;left:0;right:0;bottom:0;padding:60px 20px 18px;background:linear-gradient(transparent,rgba(20,10,8,.78))}
.slide .d{display:inline-block;background:var(--grad);border-radius:999px;padding:4px 11px;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}
.slide .nm{display:block;font:400 46px/1 "Instrument Serif",serif;margin:8px 0 3px}
.slide .br{display:block;font-size:14px;opacity:.9}
.slide .go{display:inline-block;margin-top:10px;font-weight:700;font-size:15px}
.dots{display:flex;justify-content:center;gap:8px;margin-top:26px}
.dots button{width:9px;height:9px;padding:0;border:0;border-radius:999px;background:rgba(31,26,23,.2);cursor:pointer;transition:width .3s,background .3s}
.dots button.on{width:26px;background:var(--accent)}
@media(min-width:900px){.band .in{grid-template-columns:1.1fr 1fr;align-items:center;gap:56px;padding:46px 22px 50px}.band h1{font-size:62px}.spot{max-width:460px}}
/* scroll reveal (only when JS runs, so no-JS browsers still see everything) */
.js .rv{opacity:0;transform:translateY(18px)}
.js .rv.in{opacity:1;transform:none;transition:opacity .7s ease,transform .7s cubic-bezier(.2,.8,.2,1)}
/* logo: the heartbeat draws itself, the toes pop in, then a glowing blip runs along the line */
.beat{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1.5s cubic-bezier(.6,0,.2,1) .1s forwards}
@keyframes draw{to{stroke-dashoffset:0}}
.toes ellipse{opacity:0;transform-box:fill-box;transform-origin:center;animation:pop .45s cubic-bezier(.3,1.6,.5,1) forwards}
.toes ellipse:nth-child(1){animation-delay:1.25s}.toes ellipse:nth-child(2){animation-delay:1.35s}
.toes ellipse:nth-child(3){animation-delay:1.45s}.toes ellipse:nth-child(4){animation-delay:1.55s}
@keyframes pop{from{opacity:0;transform:scale(.3)}to{opacity:1;transform:none}}
.blip{stroke-dasharray:.05 2;stroke-dashoffset:.05;opacity:0;filter:drop-shadow(0 0 3px #FF7A5C);animation:blip 3.2s linear 2s infinite}
@keyframes blip{0%{opacity:1;stroke-dashoffset:.05}60%{opacity:1;stroke-dashoffset:-1}61%,100%{opacity:0;stroke-dashoffset:-1}}
@media (min-width:900px){
h1{font-size:72px}
.pets{gap:18px 22px}
.pet{grid-template-columns:120px 1fr;padding:16px}.pet img,.pet .noimg{width:120px;height:120px}
.dwrap{padding:36px 22px 0}.dwrap .detail{padding:0}.detail h1{font-size:76px}
}
/* site dog (sprite engine, 2026-10-20): wanders on its own, runs/trots/skips, hops onto cards and off again.
   Frames come from dog-sprite.png (grid = design/sprite_template.py ROWS, 8 columns x 7 rows, square cells). */
.dog{position:fixed;left:0;top:0;z-index:25;width:100px;height:100px;display:none;background-repeat:no-repeat;
transform-origin:36.67% 83.33%;will-change:transform;cursor:pointer;-webkit-tap-highlight-color:transparent}
.js .dog{display:block}
.dog.left>span{transform:scaleX(-1)}
.dog .ht{position:absolute;left:55%;top:18%;color:#D9472F;font-size:20px;line-height:1;opacity:0;pointer-events:none}
.dog.love .ht{animation:hpop 1.3s ease-out}
@keyframes hpop{0%{opacity:0;translate:0 10px;scale:.4}30%{opacity:1;translate:0 0;scale:1}100%{opacity:0;translate:0 -22px}}
.dog .zz{position:absolute;left:62%;top:22%;font:italic 700 16px/1 "Source Sans 3",sans-serif;color:#C4304F;opacity:0;pointer-events:none}
.dog.sleep .zz{opacity:1}.dog .zz i{font-style:inherit;display:inline-block;animation:zz 2.4s ease-in-out infinite}
.dog .zz i:nth-child(2){animation-delay:.8s;font-size:.85em}.dog .zz i:nth-child(3){animation-delay:1.6s;font-size:.7em}
@keyframes zz{0%{opacity:0;transform:translate(0,6px)}40%{opacity:1}100%{opacity:0;transform:translate(6px,-12px)}}
@media(min-width:900px){.dog{width:130px;height:130px}}
@media print{.dog{display:none!important}}
@media (prefers-reduced-motion:reduce){.dog{display:none!important}*,*::before{animation:none!important;transition:none!important}
.beat{stroke-dashoffset:0}.toes ellipse{opacity:1}.js .rv{opacity:1;transform:none}.blip{display:none}}
"""

HEART = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 21s-7.5-4.6-9.6-9.2C.8 8.3 3 4.5 6.7 4.5'
         'c2.1 0 3.6 1.1 4.3 2.4h2c.7-1.3 2.2-2.4 4.3-2.4 3.7 0 5.9 3.8 4.3 7.3C19.5 16.4 12 21 12 21z"/></svg>')


BRAND_DIR = Path(__file__).resolve().parent / "brand"
_MARK_PATH = (BRAND_DIR / "path.txt").read_text().strip()
_MARK_TOES = (BRAND_DIR / "toes.txt").read_text().strip()


def mark_svg(uid, cls="", blip=False):
    """The logo mark inline (so it can animate): heartbeat line that becomes a paw."""
    b = (f'<path class="blip" pathLength="1" d="{_MARK_PATH}" stroke="#FFB59F" stroke-width="7" '
         f'stroke-linecap="round" stroke-linejoin="round"/>') if blip else ""
    return (f'<svg class="{cls}" viewBox="0 0 240 100" fill="none" aria-hidden="true"><defs>'
            f'<linearGradient id="{uid}" gradientUnits="userSpaceOnUse" x1="0" x2="240">'
            f'<stop offset="0" stop-color="#D9472F" stop-opacity="0"/><stop offset=".3" stop-color="#D9472F"/>'
            f'<stop offset="1" stop-color="#C4304F"/></linearGradient></defs>'
            f'<path class="beat" pathLength="1" d="{_MARK_PATH}" stroke="url(#{uid})" stroke-width="5.5" '
            f'stroke-linecap="round" stroke-linejoin="round"/>{b}'
            f'<g class="toes" stroke="#C93A3F" stroke-width="5.5">{_MARK_TOES}</g></svg>')


def wordmark():
    return 'Fading <i class="grad">Heartbeats</i>'


REVEAL_JS = """<script>(()=>{const els=[...document.querySelectorAll(".rv")];
if(!("IntersectionObserver" in window)){els.forEach(e=>e.classList.add("in"));return}
const io=new IntersectionObserver(es=>es.forEach(en=>{if(en.isIntersecting){en.target.classList.add("in");io.unobserve(en.target)}}),{rootMargin:"0px 0px -6% 0px"});
els.forEach((e,i)=>{e.style.transitionDelay=(i%2)*90+"ms";io.observe(e)})})()</script>"""


SPOT_JS = """<script>(()=>{const sp=document.querySelector(".spot");if(!sp)return;
const sl=[...sp.querySelectorAll(".slide")],dt=[...sp.querySelectorAll(".dots button")],n=sp.querySelector(".lbl span");if(sl.length<2)return;
let i=0,hold=0;const go=k=>{sl[i].classList.remove("on");dt[i].classList.remove("on");i=(k+sl.length)%sl.length;
sl[i].classList.add("on");dt[i].classList.add("on");if(n)n.textContent=(i+1)+" of "+sl.length};
dt.forEach((b,k)=>b.onclick=()=>{go(k);hold=Date.now()+8000});
sp.addEventListener("mouseenter",()=>hold=1e15);sp.addEventListener("mouseleave",()=>hold=0);
sp.addEventListener("touchstart",()=>hold=Date.now()+8000,{passive:true});
if(matchMedia("(prefers-reduced-motion: reduce)").matches)return;
setInterval(()=>{if(Date.now()>hold&&!document.hidden)go(i+1)},4500)})()</script>"""


def dog_html(root=""):
    return (f'<div class="dog" aria-hidden="true" style="background-image:url({root}dog.png)">'
            '<span class="zz"><i>z</i><i>z</i><i>z</i></span><span class="ht">&#9829;</span></div>')


# Dog engine (art: owner's puppy frames packed by design/dog_art.py into one strip, cell = frame number - 1).
# Only jump art exists so far; run/trot/skip/nap reuse jump frames as stand-ins until those rows arrive.
DOG_JS = """<script>(()=>{const d=document.querySelector(".dog");if(!d)return;
if(matchMedia("(prefers-reduced-motion: reduce)").matches){d.remove();return}
const N=23,RUN0=12,RUNN=6,FOOT=250/300,CX=110/300;
const STRIDE={run:[.40,.20],skip:[.55,.34]};/* bounding: one hop per stride = [seconds, hop height x size], run frames 1-6 play across each hop */
const A={stand:[[11]],look:[[7]],sit:[[0]],paw:[[6]],sniff:[[11]],lie:[[0]],sleep:[[0]],stretch:[[9]],
run:[[10,3,11],10],trot:[[11,7],4],skip:[[11,3],5],hop:[[11,3],6]};
const SPEED={run:300,trot:60,skip:130},BOB={run:.10,trot:.025,skip:.16,hop:.2};
let S=d.offsetWidth,x=innerWidth*(.15+Math.random()*.3),y=innerHeight-10,face=1,on=null,off=0;
let st="stand",t0=0,until=0,goal=null,after=null,plan=[],J=null,last=0;const prevTop=new WeakMap();
const now=()=>performance.now(),K=()=>S/110,R=a=>a[Math.random()*a.length|0];
const topLimit=()=>{const tb=document.querySelector(".topbar");return(tb?tb.getBoundingClientRect().bottom:0)+S*.75};
const groundY=()=>innerHeight-8;
const perches=()=>[...document.querySelectorAll(".pet,.sq,.facts,.empty")];
const usable=el=>{if(!el||!el.isConnected)return false;const r=el.getBoundingClientRect();
return r.width>S*1.2&&r.top>topLimit()&&r.top<groundY()-S*.5&&r.left<innerWidth-S&&r.right>S};
const bounds=el=>{if(el){const r=el.getBoundingClientRect();return[Math.max(r.left+S*.3,S*.4),Math.min(r.right-S*.3,innerWidth-S*.4)]}return[S*.4,innerWidth-S*.4]};
const set=(s,ms)=>{st=s;t0=now();until=t0+(ms||0);d.classList.toggle("sleep",s==="sleep")};
const walkTo=(tx,mode,then)=>{const[lo,hi]=bounds(on);goal=Math.min(hi,Math.max(lo,tx));after=then||null;set(mode)};
/* jump: UP = sit back (8) -> rear up, front paws in the air (7) -> spring (10) -> stretch (4) -> reach (11) -> land (12)
         DOWN = peek -> hop off -> fall nose-down -> FRONT paws land -> back end drops (land cells 18-22; phase value 2 = on the ground) */
const UP=[[.20,7,0],[.26,6,0],[.12,9,.15],[.22,3,.6],[.22,10,1],[.18,11,2]],DOWN=[[.14,18,0],[.2,19,.4],[.2,20,1],[.16,21,2],[.24,22,2]];
function jumpTo(el){const r=el?el.getBoundingClientRect():null,[lo,hi]=bounds(el);const tx=Math.min(hi,Math.max(lo,x+(Math.random()-.5)*S*1.5));
if(Math.abs(tx-x)>S*3){walkTo(tx-Math.sign(tx-x)*S*1.5,"run",()=>usable(el)||!el?jumpTo(el):next());return}
const ty=el?r.top:groundY(),upw=ty<y-4;J={el,ox:el?tx-r.left:tx,sx:x,sy:y,t:0,seq:upw?UP:DOWN};face=tx>=x?1:-1;set(upw?"up":"down")}
function hopDown(){const below=perches().filter(e=>e!==on&&usable(e)&&(()=>{const r=e.getBoundingClientRect();return r.top>y+S*.3&&r.left<x&&r.right>x})());
on=null;jumpTo(below.length?below[0]:null)}
function next(){goal=null;after=null;if(plan.length){const[s,ms]=plan.shift();return set(s,ms)}
const r=Math.random(),[lo,hi]=bounds(on),rx=()=>lo+Math.random()*(hi-lo);
if(r<.25){const c=perches().filter(e=>e!==on&&usable(e));if(c.length)return jumpTo(R(c))}
if(r<.32&&on)return hopDown();
if(r<.52)return walkTo(rx(),"run");
if(r<.64)return walkTo(rx(),"trot",()=>set("sniff",1500));
if(r<.74)return walkTo(rx(),"skip");
if(r<.80){plan=[["sleep",6000+Math.random()*6000],["stretch",900]];return set("lie",800)}
set(R(["sit","paw","look","stand"]),1600+Math.random()*2600)}
function frameOfJump(){let t=J.t,acc=0;for(const[dur,f,p]of J.seq){if(t<acc+dur)return[f,p,(t-acc)/dur,acc];acc+=dur}return null}
function tick(){const n=now(),dt=Math.min(.05,(n-(last||n))/1000);last=n;S=d.offsetWidth;let fr=null,lift=0;
if(on){if(!on.isConnected)hopDown();else{const r=on.getBoundingClientRect();
if(r.top>groundY()){on=null}else if(r.top<topLimit()&&!J){hopDown()}else{y=r.top;x=r.left+off}}}
if(!on&&!J){y=groundY();/* a card scrolling up from below lifts the dog when its top edge reaches the dog's feet */
for(const e of perches()){const r=e.getBoundingClientRect(),pt=prevTop.get(e);prevTop.set(e,r.top);
if(pt!==undefined&&pt>y&&r.top<=y&&r.left+S*.2<x&&r.right-S*.2>x){on=e;off=x-r.left;y=r.top;if(goal!==null){goal=null;after=null;set("stand",700)}break}}}
else perches().forEach(e=>prevTop.set(e,e.getBoundingClientRect().top));
if(J){if(J.el&&!usable(J.el)&&J.t<.4)J.el=null;const r=J.el?J.el.getBoundingClientRect():null;
const tx=r?r.left+J.ox:J.ox,ty=r?r.top:groundY();J.t+=dt;const ph=frameOfJump();
if(!ph){x=tx;y=ty;on=J.el;off=r?x-r.left:0;J=null;set("stand",500+Math.random()*700)}
else{const[f,p,k]=ph;fr=f;const prog=Math.min(1,Math.max(0,p===0?0:p));
/* air arc: between first lifting phase and landing */const total=J.seq.reduce((a,s)=>a+s[0],0),start=J.seq.findIndex(s=>s[2]>0);
const ta=J.seq.slice(0,start).reduce((a,s)=>a+s[0],0),gi=J.seq.findIndex(s=>s[2]===2),te=J.seq.slice(0,gi<0?J.seq.length-1:gi).reduce((a,s)=>a+s[0],0);
const q=Math.min(1,Math.max(0,(J.t-ta)/(te-ta))),h=S*.5+Math.max(0,J.sy-ty)*.5;
if(J.t>=ta&&J.t<te){x=J.sx+(tx-J.sx)*q;y=J.sy+(ty-J.sy)*q-h*4*q*(1-q)}else if(J.t>=te){x=tx;y=ty}}}
else if(goal!==null){const sp=(SPEED[st]||100)*K(),dx=goal-x;face=dx>=0?1:-1;
if(Math.abs(dx)<=sp*dt){x=goal;const f=after;goal=null;after=null;f?f():set("stand",400+Math.random()*900)}else x+=Math.sign(dx)*sp*dt;
if(on)off=x-on.getBoundingClientRect().left}
else if(n>until)next();
if(fr===null&&STRIDE[st]&&goal!==null){const[per,hh]=STRIDE[st],ph=((n-t0)/1000/per)%1;
fr=RUN0+Math.min(RUNN-1,Math.floor(ph*RUNN));lift=Math.sin(Math.PI*ph)*hh*S}
if(fr===null){const a=A[st]||A.stand,fs=a[0],fps=a[1]||0,i=fps?Math.floor((n-t0)/1000*fps)%fs.length:0;fr=fs[i];
if(BOB[st])lift=Math.abs(Math.sin((n-t0)/1000*(fps||5)*Math.PI/fs.length*fs.length))*BOB[st]*S}
d.style.backgroundSize=N*S+"px "+S+"px";d.style.backgroundPosition=-fr*S+"px 0";
d.style.transform="translate3d("+(x-S*CX).toFixed(1)+"px,"+(y-S*FOOT-lift).toFixed(1)+"px,0) scaleX("+face+")";
requestAnimationFrame(tick)}
d.addEventListener("click",()=>{if(J)return;plan=[];goal=null;set("hop",900);d.classList.remove("love");void d.offsetWidth;d.classList.add("love")});
addEventListener("scroll",()=>{if(st==="sleep"||st==="lie"){plan=[];set("stretch",700)}},{passive:true});
window.__dog={state:()=>({st,x:Math.round(x),y:Math.round(y),on:on?on.className:null,jumping:!!J,frame:J&&frameOfJump()?frameOfJump()[0]+1:null}),
jump:()=>{const c=perches().filter(usable);if(c.length)jumpTo(c[0])},floor:()=>{on=null;J=null;goal=null;set("stand",4000)}};
set("stand",1200);requestAnimationFrame(tick)})()</script>"""


def page(title, body, active, root="", wide=False, meta="", band=""):
    links = [("index.html", "Animals", "list"), ("help.html", "How to help", "help")]
    if SHOW_REMEMBERED:
        links.append(("remembered.html", "Remembered", "mem"))
    nav = "".join(f'<a href="{root}{h}" class="{"on" if k == active else ""}">{t}</a>' for h, t, k in links)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="hb-built" content="{BUILT}">
<title>{e(title)}</title>{meta or f'<meta name="description" content="{e(TAGLINE)}"><meta property="og:title" content="{e(SITE_NAME)}"><meta property="og:description" content="{e(TAGLINE)}"><meta property="og:image" content="{SITE_URL}/og.png"><meta name="twitter:card" content="summary_large_image">'}
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="icon" href="{root}icon.svg" type="image/svg+xml"><link rel="apple-touch-icon" href="{root}apple-touch-icon.png">
<meta name="theme-color" content="#FBF7F3"><script>document.documentElement.classList.add("js")</script>
<style>{CSS}</style></head><body>
<div class="topbar"><div class="in"><a class="brand" href="{root}index.html" aria-label="{e(SITE_NAME)} home">{mark_svg("mk-nav")}<span>{wordmark()}</span></a><nav class="links" aria-label="Main">{nav}</nav></div></div>
{band}<div class="wrap{" wide" if wide else ""}">
{body}
<footer>{e(SITE_NAME)} · {e(DOMAIN)}<br>We are not a shelter. Every animal's details and photo come from the shelter that has them;
please contact that shelter directly. We update this list several times a day, so it can be a few hours behind the shelter.<br><a href="{root}privacy.html">Privacy</a> · Updated {BUILT_LABEL}</footer>
</div>{dog_html(root) if SHOW_DOG else ""}{REVEAL_JS}{SPOT_JS if band else ""}{DOG_JS if SHOW_DOG else ""}</body></html>"""


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
            rows.append(f"""<a class="pet rv" href="{root}animals/{e(p['id'])}.html">{photo(p, root)}
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


def spot_pets(pets):
    """Who is featured in the home square: every animal whose shelter date is TODAY.
    If nobody is due today, the next day that has anyone (so the square is never empty while dates exist).
    Returns (animals, label)."""
    dated = [p for p in pets if p["days"] is not None and p["days"] >= 0]
    if not dated:
        return [], ""
    day = 0 if any(p["days"] == 0 for p in dated) else min(p["days"] for p in dated)
    picks = sorted((p for p in dated if p["days"] == day), key=lambda p: (p["img"] is None, p["name"]))
    label = "Out of time today" if day == 0 else "Out of time tomorrow" if day == 1 else f"Out of time {picks[0]['deadline']:%A}"
    return picks, label


def spotlight(pets, root=""):
    picks, label = spot_pets(pets)
    if not picks:
        return ""
    slides = "".join(
        f'<a class="slide{" on" if k == 0 else ""}" href="{root}animals/{e(p["id"])}.html">'
        + (f'<img src="{root}img/{e(p["img"].name)}" alt="Photo of {e(p["name"])}">' if p["img"]
           else '<div class="noimg" role="img" aria-label="No photo yet"></div>')
        + f'<span class="cap"><span class="d">{e(when(p))}</span><span class="nm">{e(p["name"])}</span>'
          f'<span class="br">{e(p["age"])} · {e(p["breed"])}</span><span class="go">Meet {e(p["name"])} →</span></span></a>'
        for k, p in enumerate(picks))
    dots = "".join(f'<button type="button" class="{"on" if k == 0 else ""}" aria-label="Show {e(p["name"])}"></button>'
                   for k, p in enumerate(picks)) if len(picks) > 1 else ""
    count = f"<span>1 of {len(picks)}</span>" if len(picks) > 1 else ""
    return (f'<div class="spot" aria-label="{e(label)}"><div class="lbl">{e(label)}{count}</div>'
            f'<div class="sq">{slides}</div><div class="dots">{dots}</div></div>')


def index_page(pets, saved, today):
    dated = sum(p["days"] is not None for p in pets)
    n_shelters = len({p["shelter"] for p in pets})
    band = f"""<section class="band"><div class="in"><div><h1>Every heartbeat deserves a <i class="grad">home.</i></h1>
<p class="lede">Dogs and cats at {n_shelters} shelter{"" if n_shelters == 1 else "s"} who are out of time or close to it. Fostering even for two weeks saves a life.</p>
<div class="pills"><span><b>{len(pets)}</b> need a way out</span><span><b>{dated}</b> have a date</span><span><b>{saved}</b> made it out recently</span></div>
{picker("", None, shelter_counts(pets))}<a class="btn" href="#list">See who needs help today</a></div>
{spotlight(pets)}</div></section>"""
    body = f'<span id="list"></span>\n{pet_sections(pets, "", show_shelter=bool(SHOW_PICKER))}'
    return page(f"{SITE_NAME}: {TAGLINE}", body, "list", wide=True, band=band)


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
    body = f"""<div class="dwrap">{photo(p, "../", "hero rv")}
<div class="detail"><span class="when{" now" if p["days"] is not None and p["days"] <= 1 else ""}">{e(("Shelter date: " + when(p)) if p["days"] is not None and p["days"] >= 0 else when(p))}</span><h1>{e(p['name'])}</h1>
<div class="actions">{main}</div>
<p class="small">Opens {e(p['name'])}'s page on the shelter's own site. Mention ID {e(p['id'])} when you contact them.</p>
{share_block(p, f"Share {p['name']}")}
<dl class="facts">{dl}</dl><div class="story">{story}</div>
<div class="actions">{mail}</div>
{share_block(p, f"Can't take {p['name']} home? Sharing helps too")}</div></div>{share_js(p)}"""
    return page(f"{p['name']} · {SITE_NAME}", body, "list", root="../", wide=True, meta=share_meta(p))


def help_page():
    body = f"""<header><h1>How you can <i class="grad">help</i></h1>
<p class="lede">You don't need a big house or a lot of money. Most of these take one afternoon.</p></header>
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


def privacy_page():
    body = """<header><h1>Privacy</h1>
<p class="lede">There are no accounts or forms here. We never ask for your name, email or payment details.</p></header>
<div class="prose">
<h2>Visit counts (Google Analytics)</h2>
<p>We use Google Analytics to see how many people visit and which animals' pages are viewed and shared. It uses cookies and collects things like the pages you view, roughly where you are (city level), and your device and browser type. It does not tell us who you are.</p>
<p>See <a href="https://policies.google.com/technologies/partner-sites">how Google uses information from sites that use its services</a>. To opt out, block cookies for this site in your browser or install the <a href="https://tools.google.com/dlpage/gaoptout">Google Analytics opt-out add-on</a>.</p>
<h2>Fonts</h2>
<p>The text uses fonts from Google Fonts, so your browser fetches them from Google's servers.</p>
<h2>Sharing</h2>
<p>The share buttons on each animal's page open the app or site you pick. Nothing is sent anywhere until you share it there yourself.</p>
<h2>Animal information</h2>
<p>Every animal's details and photo come from the public listings of the shelter that has them.</p>
<p>Last updated October 27, 2026.</p>
</div>"""
    return page(f"Privacy · {SITE_NAME}", body, "privacy")


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

def add_analytics(f: Path):
    """Put the Google tag at the top of <head>. A page without a <head> fails the build rather than going untracked."""
    page = f.read_text()
    if f"gtag/js?id={GA_ID}" in page:
        return
    m = re.search(r"<head[^>]*>", page, re.I)
    if not m:
        raise ValueError(f"{f}: no <head>, can't add the analytics tag")
    f.write_text(page[:m.end()] + "\n" + GA_TAG + page[m.end():])


def build(out: Path = OUT, today: date = None, show_remembered: bool = None, show_picker: bool = None,
          show_dog: bool = None, built_at: datetime = None):
    global SHOW_REMEMBERED, SHOW_PICKER, SHOW_DOG, BUILT, BUILT_LABEL
    built_at = (built_at or datetime.now(DEFAULT_TZ)).astimezone(DEFAULT_TZ)
    BUILT = built_at.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
    BUILT_LABEL = built_at.strftime("%b %-d, %-I:%M %p CT")
    if show_remembered is not None:
        SHOW_REMEMBERED = show_remembered
    if show_dog is not None:
        SHOW_DOG = show_dog
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
    for src, dst in (("dog-all.png", "dog.png"), ("icon.svg", "icon.svg"), ("apple-touch-icon.png", "apple-touch-icon.png"), ("og-1200x630.png", "og.png")):
        if (BRAND_DIR / src).exists() and (SHOW_DOG or dst != "dog.png"):
            shutil.copy2(BRAND_DIR / src, tmp / dst)
    (tmp / "index.html").write_text(index_page(pets, saved, today))
    for name, info in SHELTERS.items():
        d = tmp / shelter_path(name)
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(shelter_page(name, info, [p for p in pets if p["raw_shelter"] == name], pets))
    (tmp / "help.html").write_text(help_page())
    (tmp / "privacy.html").write_text(privacy_page())
    if SHOW_REMEMBERED:
        (tmp / "remembered.html").write_text(remembered_page(gone))
    if SHOW_DOG:
        import importlib.util as _u  # dog animation test page (not linked from the site)
        _spec = _u.spec_from_file_location("dog_lab", Path(__file__).resolve().parent / "dog_lab.py")
        _lab = _u.module_from_spec(_spec); _spec.loader.exec_module(_lab); _lab.build(tmp)
        _spec = _u.spec_from_file_location("dog_lab24", Path(__file__).resolve().parent / "dog_lab24.py")  # 24 fps lab
        _lab = _u.module_from_spec(_spec); _spec.loader.exec_module(_lab); _lab.build(tmp)
    for f in tmp.rglob("*.html"):
        add_analytics(f)
    if out.exists():
        shutil.rmtree(out)
    tmp.rename(out)
    return {"out": str(out), "at_risk": len(pets), "remembered": len(gone),
            "no_adopt_link": sum(not p["adopt"] for p in pets), "shelter_pages": len(SHELTERS), "built": BUILT}


if __name__ == "__main__":
    print(build())
