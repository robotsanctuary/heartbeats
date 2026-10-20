# AGENTS.md: Heartbeats / Fading Heartbeats

Notes for any agent (or person) picking this project up.

## What this is
Scrapes Texas shelter at-risk (euthanasia-deadline) feeds into a private local
SQLite DB and builds the public site **Fading Heartbeats** (fadingheartbeats.com,
tagline "Every heartbeat deserves a home."). Nothing is published yet.

## Current status (2026-10-19)
- Live: Dallas Animal Services scraper, run by Hermes cron at 9am/3pm/9pm Central
  (9pm also sends a Telegram summary). Run log: `RUN_LOG_PATH` (.env).
- Site preview: `python design/build_site.py` builds 4 pages (list, animal detail,
  how to help, Remembered) into `/Volumes/Extreme/heartbeats-data/site-preview`.
  `design/shoot.sh` makes phone-width screenshots.
- Adopt links are per shelter in `shelters/registry.py` (no link if a shelter isn't registered).
- 85 offline tests: `python -m pytest`.
- Texas expansion research: `docs/texas-shelter-survey.md`.

## Next steps
1. Hosting: Cloudflare (same account as the owner's other sites). The domain stays
   at Porkbun and its nameservers point to Cloudflare. A static Worker goes to a
   private test URL first. Ask the owner before deploying.
2. Add city/state/lat-lon to the registry (for a future US map; the map itself is
   deferred until ~5-10 Texas shelters).
3. Next shelters: Fort Worth, San Antonio, Austin, then Abilene and El Paso.
4. Data review ~2026-10-26.

## Rules
- Only `db.py` opens the DB; timestamps are canonical UTC strings.
- An empty feed never archives animals. Unknown outcomes go to PENDING_VERIFICATION.
  EUTHANIZED (and so the Remembered page) is set only by a human.
- Large data/photos live on /Volumes/Extreme, never in git. Never commit `.env`/`.db`.
- Pre-commit secret hook: `git config core.hooksPath .githooks`.
