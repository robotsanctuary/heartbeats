# AGENTS.md: Heartbeats / Fading Heartbeats

Notes for any agent (or person) picking this project up.

## What this is
Scrapes Texas shelter at-risk (euthanasia-deadline) feeds into a private local
SQLite DB and builds the public site **Fading Heartbeats** (fadingheartbeats.com,
tagline "Every heartbeat deserves a home."). Nothing is published yet.

## Current status (2026-10-23)
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
  /Users/ghost/venv/bin/python3 -m http.server 8787 --bind 0.0.0.0` -> http://<Wi-Fi IP from `ipconfig getifaddr en1`>:8787
- 96 offline tests: `python -m pytest`.
- Texas expansion research: `docs/texas-shelter-survey.md`.

## Next steps
1. **Header: DONE.** Option B: full-width sticky `.topbar`; home pink `.band` with text left and a
   daily `.spot` square (animals due today; if none, next closest day — owner confirmed). `SPOT_JS`.
2. **Site dog: 24 fps pitbull engine, pieces 1-5 DONE on the test page, NOT on the live site yet.**
   - Live site still uses the **golden puppy** in `DOG_JS`. Do NOT switch until the owner says so.
   - Engine: `design/dog24.js`; test page `dog-play24.html` (fake scrolling cards; built by
     `design/dog_lab24.py`, also by build_site.py). Art packer `design/pack24.py` (sources in
     `/Volumes/Extreme/heartbeats-data/art-inbox/`, output `design/brand/dog24*/`); joins/entry tables
     `design/dog24_data.py` -> `engine.json`. Use the lossy set (`dog24-lossy/`, owner approved).
   - Pieces: 1 walk, 2 random floor tricks, 3 solid cards (sniff/paw/hop up), 4 ride cards + jump down,
     5 stays on screen (owner's turn-around art, mirrored left-facing logic, phone vs laptop at 900px).
     Piece 5 = 829ba61, owner approved 2026-10-23.
   - Piece 6 (2026-10-23, waiting on the owner): owner's walk->run / run->walk art (`w2r`, `r2w`, hand-offs from
     their meta.json) as a floor trick "run" (speeds up, 1-5 strides, slows down; must fit before the next card /
     turn zone, so laptops only: phone screens are too narrow for both transitions) + any run slows with the art
     when room runs short. One-paw "pick me" (`pawone` + `pawoneloop`, measured joins) = 3rd card-side wait.
     Fix: a non-hoppable card the dog already stands in front of no longer hides the next card (dog walked through).
   - Next (not started, ask the owner): wiring the pitbull engine into the real site (real `.pet` cards
     instead of `.card24`, lazy sheet loading), hover/tap tricks, art still pending (run->walk stop,
     one-paw "pick this dog", sleep).
   - Details and pitfalls: Hermes skill `heartbeats-shelter-aggregator` + its `references/site-dog-animation.md`.
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
