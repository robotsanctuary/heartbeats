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
1. **Header: DONE 2026-10-20 (option B + daily scroller).** Full-width sticky `.topbar` (logo left,
   menu right) on every page; home page has a full-width pink `.band` (headline, stat pills, "See who
   needs help today") and an "Out of time soonest" scroller of photo tiles (`reel_pets()`: photos only,
   soonest date first, past-date first, max `REEL_MAX`=20, tops up with no-date animals below `REEL_MIN`=8).
   It is rebuilt with the site, so it changes every day. Auto-drifts sideways (`REEL_JS`, loops via cloned
   tiles), pauses on touch/hover, off under reduced motion. Old A/C mockups kept in
   `/Volumes/Extreme/heartbeats-data/mockups/header-options/`.
2. **Scrolling dogs (owner wants it):** small subtle dog(s) that run along the bottom as the
   user scrolls and, when scrolling stops, do random actions (sit, wave, give paw, wag, nap,
   second dog/cat joins); tap = wiggle; off for reduced motion. Art source undecided:
   recommended a custom dog in the logo's line style, one dog with 4-5 moves first.
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
