# AGENTS.md: Heartbeats / Fading Heartbeats

Notes for any agent (or person) picking this project up.

## What this is
Scrapes Texas shelter at-risk (euthanasia-deadline) feeds into a private local
SQLite DB and builds the public site **Fading Heartbeats** (fadingheartbeats.com,
tagline "Every heartbeat deserves a home."). Nothing is published yet.

## Current status (2026-10-20)
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
1. **Header: DONE 2026-10-20 (option B + "Out of time today" spotlight).** Full-width sticky `.topbar`
   on every page. Home has a full-width pink `.band`: text left; on the right (below on phones) a big
   square `.spot` that cycles through ONLY the animals whose shelter date is today (`spot_pets()`; if
   nobody is due today it shows the next day that has anyone, labelled e.g. "Out of time tomorrow").
   Crossfade + slow zoom every 4.5s, dots to jump, pauses on hover/touch, no auto-advance under
   reduced motion (`SPOT_JS`). Rebuilt with the site, so it changes daily.
2. **Site dog: sprite engine BUILT 2026-10-20 (owner testing, real art coming).** `dog_html()` + `DOG_JS`
   in build_site.py draw frames from `design/brand/dog-sprite.png` (8 cols x 7 rows, square cells, same
   rows as `design/sprite_template.py` ROWS: run, trot, skip, jump up, jump down, idle, rest). Placeholder
   sheet: `python design/sprite_template.py --sheet`; template for the owner's image generator:
   `python design/sprite_template.py`. The dog wanders by itself (run/trot+sniff/skip/sit/paw/look/nap),
   jumps onto cards (`.pet,.sq,.facts,.empty` top edges), rides them while scrolling and hops down
   (to a lower card or the floor) when its card reaches the top bar. Tap = happy hop + heart; scrolling
   wakes it. Debug: `window.__dog.state()` / `__dog.jump()`. Off for reduced motion + print.
   To drop in new art: replace dog-sprite.png keeping the grid, then tune `FOOT` (feet height in a cell)
   and `CX` (body centre) in DOG_JS.
3. Small polish: "More…" share button alone on its row; check nav edge on wide screens.
4. Hosting: Cloudflare (same account as the owner's other sites). The domain stays
   at Porkbun and its nameservers point to Cloudflare. A static Worker goes to a
   private test URL first. Ask the owner before deploying. Owner wants everything
   checked on the LAN preview before launch.
5. Next shelters: Fort Worth (awaiting go-ahead), San Antonio, Austin, then Abilene and El Paso.
6. Open questions for owner: [draft] copy wording; show shelter descriptions verbatim?
7. Data review ~2026-10-26.

## Rules
- Only `db.py` opens the DB; timestamps are canonical UTC strings.
- An empty feed never archives animals. Unknown outcomes go to PENDING_VERIFICATION.
  EUTHANIZED (and so the Remembered page) is set only by a human.
- Large data/photos live on /Volumes/Extreme, never in git. Never commit `.env`/`.db`.
- Pre-commit secret hook: `git config core.hooksPath .githooks`.
