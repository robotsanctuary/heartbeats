# AGENTS.md: Heartbeats / Fading Heartbeats

Notes for any agent (or person) picking this project up.

## What this is
Scrapes Texas shelter at-risk (euthanasia-deadline) feeds into a private local
SQLite DB and builds the public site **Fading Heartbeats** (fadingheartbeats.com,
tagline "Every heartbeat deserves a home."). Nothing is published yet.

## Current status (2026-10-21, paused for another task)
- Live: Dallas Animal Services scraper, run by Hermes cron at 9am/3pm/9pm Central
  (9pm also sends a Telegram summary). Run log: `RUN_LOG_PATH` (.env).
- Site preview: `python design/build_site.py` builds into
  `/Volumes/Extreme/heartbeats-data/site-preview`: list, animal pages, How to help,
  one page per shelter (`/tx/dallas/`). Remembered is built only with `SHOW_REMEMBERED=1`
  (hidden until announced). Shelter menu + shelter line on cards appear automatically at 2+ shelters.
- Done 2026-10-20: desktop layout (2-col list, side-by-side animal page), share row per
  animal (Text/Email/Facebook/X/WhatsApp/Copy/More + link-preview tags), shelter
  location fields + per-shelter pages, new logo + icons (`design/brand/`), modern restyle
  (Instrument Serif + gradient italic "option 6", gradient bg, white cards, animations).
- Phone/laptop review server (LAN only): `cd /Volumes/Extreme/heartbeats-data/site-preview &&
  /Users/ghost/venv/bin/python3 -m http.server 8787 --bind 0.0.0.0` -> http://192.168.1.71:8787
- 96 offline tests: `python -m pytest`.
- Texas expansion research: `docs/texas-shelter-survey.md`.

## Next steps
1. **Header: DONE.** Option B: full-width sticky `.topbar`; home pink `.band` with text left and a
   daily `.spot` square (animals due today; if none, next closest day — owner confirmed). `SPOT_JS`.
2. **Site dog: IN PROGRESS on dog-lab.html, NOT on the live site yet.**
   - Live site still uses the **golden puppy** (jump + landing + bounding run) in `DOG_JS`.
   - Owner prefers the **pitbull** art (walk/run/sit/jump zips, real RGBA). Do NOT switch `DOG_JS`
     until they say so.
   - Lab: `http://192.168.1.71:8787/dog-lab.html` (rebuild: `$PY design/build_site.py`).
     Interactive: hover/tap dog takes turns: (A) sit -> paw up -> hold -> stand, (B) belly-rub roll -> wiggle -> roll back; then walks on.
     Last request (in lab, commit pending if not already): jump up/down **three box heights**
     (tall 130px / medium 80px / small 35px).
   - Owner jump-down set (21 frames) in lab: own box + used for the DOWN half of the 3-height course.
   - Owner lie-down set (27 + 6 idle) in lab. Still missing: sleep (head down, eyes closed) + get-up; optional sit hold with paw DOWN.
   - Puppy walk attempts failed (back legs never step); code-rig walk rejected. Inventory:
     `design/brand/DOG_ART_INVENTORY.md`. Packer: `design/dog_art.py` (move un-numbered sheets
     into `orig/`). Combine: `python design/dog_art.py --combine jump run land walk frolic walkmix pitbull pitbullrun pitbullsit pitbulljump pitbulljumpdown pitbullliedown pitbullbellyrub` (jumpdown is packed by `dog_art.build_travel`, see inventory)
   - HOLD Cloudflare hosting and Fort Worth scraper until design is locked.
3. Hosting (later): Cloudflare Worker, private test URL first. Ask before deploying.
4. Next shelters after go-ahead: Fort Worth, San Antonio, Austin, Abilene, El Paso.
5. Open: [draft] copy; verbatim shelter descriptions?
6. Data review ~2026-10-26.

## Rules
- Only `db.py` opens the DB; timestamps are canonical UTC strings.
- An empty feed never archives animals. Unknown outcomes go to PENDING_VERIFICATION.
  EUTHANIZED (and so the Remembered page) is set only by a human.
- Large data/photos live on /Volumes/Extreme, never in git. Never commit `.env`/`.db`.
- Pre-commit secret hook: `git config core.hooksPath .githooks`.
