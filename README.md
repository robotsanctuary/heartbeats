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

See the full setup walkthrough in this project's conversation history,
or follow this short version:

1. Install Postgres locally (ideally on an external drive you control)
2. `cp .env.example .env` and fill in `LOCAL_DATABASE_URL` + `OPENAI_API_KEY`
3. `psql "$LOCAL_DATABASE_URL" -f schema.sql`
4. `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
5. `python -m shelters.texas.dallas --write`
6. `python accuracy_report.py` to confirm it worked

## Architecture

- **Local Postgres** (your machine only, never exposed to the internet) --
  where all scraping, review, and accuracy tracking happens
- **Remote Postgres** (hosted separately) -- receives only vetted,
  approved data via `publish.py`; this is what the public website reads from
- **`shelters/{state}/{shelter}.py`** -- one script per shelter,
  sharing common logic via `shelters/common.py`

## Files

| File | Purpose |
|---|---|
| `schema.sql` / `schema.prisma` | Local database schema |
| `schema_remote.sql` | Remote (public-facing) database schema |
| `shelters/` | Per-shelter scraper scripts |
| `matching_logic.py` | Matches social-media posts to known animals |
| `ai_extractor.py` | Extracts structured data from messy social captions |
| `accuracy_report.py` | Review queue + confidence tracking |
| `image_archive.py` | Downloads and retains animal photos locally |
| `publish.py` | Pushes vetted data from local to remote |
| `moderate.py` | Reviews public comments/submissions (remote) |
