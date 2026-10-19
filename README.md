# Heartbeats

At-risk animal aggregator: pulls euthanasia-deadline data directly from
shelter systems, reviews it for accuracy, and (eventually) publishes it
to a public site so people can help before it's too late.

## Status

Currently working: Dallas Animal Services (`shelters/texas/dallas.py`),
pulling two live, validated data feeds directly from their shelter
software. Everything downstream of that -- local review, the remote
database, the public website -- is designed but not yet running.

## Setup

Short version:

1. Python 3.10+ required (macOS's built-in 3.9 is too old).
   `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
2. `cp .env.example .env` and set `LOCAL_DB_PATH` (where the SQLite file lives) + the `LLM_*` settings
   (local LM Studio/Ollama or OpenAI). Never commit `.env` or put real
   passwords in `.env.example`.
3. `python db.py init` (creates the database; the scraper also does this automatically)
4. `python -m shelters.texas.dallas` for a dry run (prints only)
5. `python -m shelters.texas.dallas --write`
6. `python db.py info` / `python accuracy_report.py` to confirm it worked
7. Tests: `pip install -r requirements-dev.txt && python -m pytest` (offline, no network or LLM needed)
8. Once per clone: `git config core.hooksPath .githooks` -- enables the
   pre-commit check that blocks real passwords/API keys from being committed

## Schedule

Runs as Hermes cron jobs (script-only, no LLM) that call
`~/.hermes/scripts/heartbeats_scrape.sh` at 9am and 3pm, and
`heartbeats_summary.sh` at 9pm (Central). Normal runs are silent; failures
and the 9pm daily summary go to Telegram. Every run appends a line to
`RUN_LOG_PATH` (default `data/runs.jsonl`). Jobs only fire while the Hermes
gateway is running.

## Architecture

- **Local SQLite** (one file on your machine, never exposed to the internet) --
  where all scraping, review, and accuracy tracking happens. `db.py` is the
  only place that opens it.
- **Remote database** (hosting not chosen yet; code currently assumes Postgres) --
  receives only vetted, approved data via `publish.py`; this is what the public
  website reads from
- **`shelters/{state}/{shelter}.py`** -- one script per shelter,
  sharing common logic via `shelters/common.py`

## Files

| File | Purpose |
|---|---|
| `db.py` | Local SQLite connection, setup (`init`/`info`), timestamp helpers |
| `schema.sql` | Local database schema (SQLite) |
| `schema_remote.sql` | Remote (public-facing) database schema |
| `shelters/` | Per-shelter scraper scripts |
| `matching_logic.py` | Matches social-media posts to known animals |
| `ai_extractor.py` | Extracts structured data from messy social captions |
| `accuracy_report.py` | Review queue + confidence tracking |
| `image_archive.py` | Downloads and retains animal photos locally |
| `publish.py` | Pushes vetted data from local to remote |
| `moderate.py` | Reviews public comments/submissions (remote) |
| `run_scheduled.py` | Scheduled entry point: runs scrapers, logs each run, prints failure alerts / the daily summary |
| `tests/` | Offline test suite (`python -m pytest`) |
