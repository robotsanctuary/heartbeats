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
2. **Site dog: owner's puppy art IN (2026-10-20).** Owner sent 12 jump frames (golden puppy,
   transparent PNGs) -> `design/brand/dog-src-jump/`, packed by `python design/dog_art.py <folder>`
   into `design/brand/dog-jump.png` (300px cells, hind feet anchored at x110,y250; build copies it to
   `dog.png`). Engine `DOG_JS`: jump UP = frames 8 sit -> 7 rear up, paws in air -> 10 spring -> 4 leap
   -> 11 reach -> 12 land, on a lower arc; jump DOWN = 12 -> 4 -> 11 -> 12. A card scrolling up from
   below now LIFTS a dog standing on the floor. Wanders, rides cards, hops off at the top bar.
   RUN art in (2nd zip, `design/brand/dog-src-run/`): packed with `--name run --frames 3,6,1,4,7,8`, then
   `python design/dog_art.py --combine jump run` -> `dog-all.png` (cells 0-11 jump, 12-17 run; build
   copies it to `dog.png`). Landing art (owner, 3 frames on one white JPG) in `dog-src-land/`: background + white border flooded out, cut into 3, scaled 0.6, packed as `landart` (anchored on FRONT paws), used as land cells 3-5. Run/skip play run frames over a bounding hop (`STRIDE`). Weakness: the run
   frames are all stretched-leap poses (no gathered-legs frame), so it reads as bounding, not galloping.
   Trot/nap/sit still use jump frames as stand-ins (owner is doing animations one at a time). Old stick-dog sheet: `design/sprite_template.py` (template only).
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
