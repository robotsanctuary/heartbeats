# At-Risk Animal Aggregator — Phase 1

This is the foundation layer: the database schema, the AI text-extraction
script, the matching logic, the accuracy/review layer, and the publish
step that ties them together. No scrapers yet — that's Phase 2.

## Architecture: local working DB + remote publish target

This is a deliberate two-database design:

```
[ Mac Mini, no inbound ports open, ever ]
  Script A + B (scrapers)
  ai_extractor.py  ──►  matching_logic.py  ──►  LOCAL Postgres
                                                  (pets, media_sources,
                                                   pending_profiles, audit_log)
                                                       │
                                          you review via accuracy_report.py
                                          + promote_pending.py
                                                       │
                                                       ▼
                                              python publish.py
                                          (one-way, outbound only)
                                                       │
                                                       ▼
                                            [ REMOTE Postgres ]
                                       only ever receives pets +
                                       media_sources -- never the
                                       raw scraping data or review notes
                                                       │
                                                       ▼
                                          Website (Vercel/etc.) reads
                                          from remote via a read-only role
```

Why this shape, specifically:
- **The Mac mini never listens for inbound connections.** It only makes
  outbound connections (to OpenAI, and to the remote DB when you choose
  to publish). There's no path for anything on the internet to reach it.
- **The remote DB only ever holds what you've already published.** It
  never receives `pending_profiles` or `audit_log` — your raw social
  post text, review reasoning, and AI decision trail stay local. If the
  remote DB or the web server reading from it is ever compromised, the
  blast radius is limited to public listing data you were going to
  publish anyway.
- **The remote DB's credentials should be scoped tightly.** Give
  `publish.py` a Postgres role that can only `INSERT`/`UPDATE` on `pets`
  and `media_sources` — not an admin connection string — so even a
  leaked `REMOTE_DATABASE_URL` can't do much damage, and give the
  website itself a separate **read-only** role.

## Files

| File | Purpose |
|---|---|
| `schema.prisma` | Prisma schema for the unified pet database (Postgres) |
| `schema.sql` | Same schema as raw SQL, if you're not using Prisma |
| `ai_extractor.py` | Sends messy social captions to GPT-4o mini, gets back clean JSON (`pet_id`, `deadline`, `shelter_name`, etc.) |
| `matching_logic.py` | Decides: append to existing pet, create a pending profile, or fuzzy-match and merge. Writes to LOCAL Postgres only. |
| `accuracy_report.py` | Shows the review queue, confidence trends, and human-verified accuracy from LOCAL Postgres |
| `promote_pending.py` | Promotes (or rejects) a reviewed `pending_profiles` row into a real `pets` row, locally |
| `publish.py` | One-way push of vetted `pets` + `media_sources` from LOCAL to REMOTE Postgres |
| `example_queries.sql` | Ready-to-use queries for the upcoming/today/euthanized views against REMOTE Postgres |
| `test_extraction_accuracy.py` | Regression test against a hand-verified golden set, to catch AI drift |
| `requirements.txt` | Python dependencies |

## 0. Working across machines (Mac mini + laptop, etc.)

This project is a git repo. Clone it wherever you're working, and keep
`.env` local to each machine (it's gitignored — never committed).

```bash
git clone https://github.com/yourname/atrisk-animal-aggregator.git
cd atrisk-animal-aggregator
cp .env.example .env
# fill in LOCAL_DATABASE_URL, REMOTE_DATABASE_URL, and OPENAI_API_KEY in .env
```

The Mac mini is where the pipeline actually runs on a schedule and where
`LOCAL_DATABASE_URL` should point at a real database (local Postgres, or
a private hosted one). A laptop you're developing from can point
`LOCAL_DATABASE_URL` at its own local Postgres, or at a scratch/dev
database — it doesn't need to be the same local DB as the Mac mini's,
since nothing about local-to-local syncing matters here. What has to
stay consistent across machines is the **code** (via git) and the
**schema** (via migrations, see below) — not the local data itself.

A few habits worth keeping:

- **Never commit `.env`.** It's already in `.gitignore`, but double
  check before your first commit if you ever create it before running
  `git init`.
- **Schema changes go through migrations, not hand-edits.** If you're
  using Prisma, run `npx prisma migrate dev --name describe_the_change`
  on whichever machine you made the change on, commit the generated
  migration file, then on the *other* machine run
  `npx prisma migrate deploy` (or `migrate dev` in development) to
  apply the same change to the shared database. This keeps
  `schema.prisma` and the live database from drifting apart, and gives
  you a history of every schema change instead of one-off manual
  `ALTER TABLE`s.
- **requirements.txt is the source of truth for Python deps.** After
  `pip install`-ing something new, add it to `requirements.txt` and
  commit, so the other machine (or your Mac mini's cron job) can
  `pip install -r requirements.txt` and stay in sync.
- **Don't develop directly on `main` once this is live and scheduled.**
  Once the Mac mini is running this unattended 3x/day, treat `main` as
  "what's currently running in production." Do a feature branch, test
  it locally (or against a scratch/staging database), merge, then pull
  on the Mac mini. This matters more here than in a typical side
  project, since a bad extraction prompt pushed straight to `main`
  could start mis-tagging animals in the pipeline that runs
  automatically.

## 1. Set up the local database

This is where all the real work happens -- scraping, extraction,
matching, review. Any local Postgres works; on a Mac mini, `brew install
postgresql@16` is the simplest option, or use Docker if you'd rather not
install it system-wide.

```bash
# Example: local Postgres via Docker (bound to localhost only by default)
docker run --name atrisk-local-db -e POSTGRES_PASSWORD=devpassword -p 127.0.0.1:5432:5432 -d postgres:16
```

Note the `127.0.0.1:5432:5432` port binding above (rather than just
`5432:5432`) -- it makes sure Docker only exposes Postgres to your own
machine, not your local network.

## 2. Set up the remote database

Use a free hosted Postgres (Supabase, Neon, or Railway) for this one.
Create a role scoped to `INSERT`/`UPDATE` on `pets` and `media_sources`
only -- this is the credential `publish.py` will use, and the smaller
its permissions, the smaller the blast radius if it's ever leaked.
Create a *second*, read-only role for the website itself to use.

## 3. Fill in your `.env`

```bash
cp .env.example .env
```

Then edit `.env` with:
- `LOCAL_DATABASE_URL` — from step 1
- `REMOTE_DATABASE_URL` — the publisher role's connection string from step 2
- `OPENAI_API_KEY`

## 4. Apply the schema to BOTH databases

The remote database needs the same `pets` and `media_sources` tables
(it doesn't need `pending_profiles` or `audit_log` at all, since those
never leave the local machine -- feel free to omit them from the remote
schema entirely).

**Option A — Prisma (recommended, gives you a typed client too):**

```bash
npm install prisma @prisma/client
npx prisma migrate dev --name init --schema=./schema.prisma   # against LOCAL_DATABASE_URL
```

**Option B — raw SQL:**

```bash
psql "$LOCAL_DATABASE_URL" -f schema.sql
psql "$REMOTE_DATABASE_URL" -f schema.sql   # or a trimmed version without pending_profiles/audit_log
```

## 5. Python environment

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 6. Try the extractor by itself

```bash
python ai_extractor.py
```

You should see two sample volunteer captions turned into structured JSON —
this is the piece Script B (the social media enricher) will call on every
post it collects.

## 7. Try the full pipeline (extraction → matching → local DB write)

Make sure your local `pets` table has at least one row to test against
(insert one manually via `psql` or a Prisma seed script), then:

```bash
python matching_logic.py
```

This runs a sample caption through `extract_pet_info()` and then
`process_extraction()`, which will either:
- append a media link to a matching pet,
- create a `pending_profiles` row (waiting on the shelter scraper or a
  fuzzy match), or
- auto-merge via fuzzy matching if a description strongly matches an
  active listing at the same shelter.

Everything above only ever touches `LOCAL_DATABASE_URL` -- nothing is
public yet.

## 8. Review, promote, and publish

```bash
python accuracy_report.py          # see what's in the review queue
python promote_pending.py <id> --pet-id A2145501 --shelter-name "Dallas Animal Services"
python promote_pending.py <id> --reject   # or reject it
python publish.py --dry-run        # see what WOULD go live
python publish.py                  # actually push to REMOTE_DATABASE_URL
python publish.py --full           # first run only: push everything, ignoring the watermark
```

`publish.py` only ever pushes `pets` and `media_sources` rows, and only
from local to remote -- it never reads anything back. It's **incremental
by default**: a local-only `publish_state` table tracks the timestamp of
the last successful push, and every run after the first only selects
rows that changed since then, instead of re-sending the whole table.
Status changes (an animal going from `AT_RISK` to `SAFE`, `ADOPTED`, or
`EUTHANIZED`) count as a change like any other edit, so they flow
through on the next run automatically. Use `--full` the very first time
you point this at a fresh remote database, or if you ever want to force
a full resync.

## 9. Dates, deadlines, and the euthanized page

Three date fields on `pets` drive everything date-related:

| Field | Meaning |
|---|---|
| `intake_date` | When the animal entered the shelter |
| `deadline_timestamp` | The scheduled/threatened euthanasia date. Can move as circumstances change, and is cleared once the animal is no longer at risk. |
| `euthanized_at` | Set once, only when `status` becomes `EUTHANIZED` -- the confirmed actual outcome date |

`example_queries.sql` has ready-to-use queries for exactly what you
described:
- **Upcoming** — `AT_RISK` pets with a future `deadline_timestamp`, soonest first
- **Today** — `AT_RISK` pets whose `deadline_timestamp` falls on the current date (the "who might be euthanized today" list)
- **Euthanized page** — pets where `status = 'EUTHANIZED'`, most recent `euthanized_at` first — the honest record of outcomes you want to show

One thing to design deliberately once Script A exists: **who actually
sets `status = 'EUTHANIZED'` and stamps `euthanized_at`.** Nothing does
this automatically yet, on purpose -- it's not something the AI
extraction/matching pipeline should ever infer from a social post; a
volunteer saying "he didn't make it" is exactly the kind of claim that
belongs behind a human confirmation, not an auto-commit. The natural
place for it is the outcome-detection part of Script A (the official
shelter scraper): when a pet_id that was `AT_RISK` disappears from a
shelter's official at-risk list, that's your signal to check the
shelter's outcome records (many publish these too) and, once confirmed,
update the local row -- not something to guess from a caption.

Also worth deciding early: shelters report deadlines in their own local
time zone, but `deadline_timestamp` is stored as UTC. "Today" should
probably mean *the shelter's* today, not UTC's -- see the note in
`example_queries.sql` for how to adjust that once you're pulling from
shelters across time zones.

## 10. The accuracy layer

Three things work together to keep bad AI/scraper output from quietly
eroding the dataset:

**Confidence gating (automatic, happens on every run)**
`matching_logic.py` no longer treats AI decisions as binary. Both the
extraction confidence and the fuzzy-match probability are checked against
two thresholds:
- **High** → auto-commit (append media, or auto-merge a fuzzy match)
- **Low** → treated as no match, filed as an ordinary pending profile
- **Middle** → flagged `needs_review = TRUE` with a `review_reason`,
  instead of guessing either way

Check what's waiting on you:
```bash
python accuracy_report.py
```
This also prints a rolling confidence trend and flags it if recent
confidence has dropped noticeably — an early signal of model drift.

**Audit trail (automatic, happens on every run)**
Every AI decision — not just successful ones — gets written to
`audit_log`, including the raw input text and the model's raw JSON
output. This is what makes the confidence trend and human-verified
accuracy numbers in `accuracy_report.py` possible, and it's your
paper trail if something looks wrong on the live site and you want to
trace back why.

As you spot-check entries, mark them:
```sql
UPDATE audit_log SET human_verdict = 'correct', reviewed_at = now() WHERE id = '...';
UPDATE audit_log SET human_verdict = 'incorrect', reviewed_at = now() WHERE id = '...';
```
`accuracy_report.py` will then report your real-world accuracy rate.

**Regression testing (run manually or on a schedule)**
```bash
python test_extraction_accuracy.py
```
Runs a small hand-verified "golden set" (`golden_dataset.json`) through
the extractor and reports pass/fail per case plus an overall accuracy
score. Exits non-zero if accuracy drops below 85%, so this can be wired
into a scheduled job that alerts you (email/Slack webhook) if a silent
OpenAI model update or a prompt change degrades quality. Add more cases
to `golden_dataset.json` over time, especially real posts that the
extractor got wrong — turning every real mistake into a permanent
regression check is the single best way to keep this from repeating.

## What's next (Phase 2)

Once this is running locally and you're comfortable with the extraction
quality, the next phase is Script A — the official shelter scraper
(Playwright/BeautifulSoup + PDF parsing) that populates the `pets` table
in the first place. Everything in Phase 1 assumes that table exists and
gets kept fresh by that scraper.
