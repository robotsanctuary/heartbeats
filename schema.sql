-- schema.sql
-- LOCAL database schema (SQLite). This is the private working/review
-- database on your own machine. The public/remote side is separate and
-- still undecided -- see schema_remote.sql.
--
-- Create it with (safe to re-run -- everything is IF NOT EXISTS):
--   python db.py init
--
-- TIMESTAMPS: SQLite has no timestamp type, so every timestamp column
-- is TEXT in ONE canonical UTC format:
--     2026-08-02T05:00:00.000Z
-- Always write timestamps through db.utcnow() / db.to_utc(). One fixed
-- format means plain text comparison sorts chronologically, which the
-- publish watermark and the scraper's grace period depend on. The CHECK
-- constraints reject any other format, so a bad timestamp fails loudly
-- instead of silently mis-sorting.
--
-- BOOLEANS are INTEGER 0/1. IDs that were UUIDs in Postgres are TEXT
-- (32 hex chars from randomblob, or a uuid4 string from Python).

-- ------------------------------------------------------------------
-- pets: one row per animal, keyed on the official shelter Pet ID
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pets (
  pet_id                  TEXT PRIMARY KEY,
  name                    TEXT,
  species                 TEXT NOT NULL DEFAULT 'DOG'
                            CHECK (species IN ('DOG', 'CAT', 'OTHER')),
  breed                   TEXT,
  age                     TEXT,     -- shelters report this inconsistently, so free text
  sex                     TEXT,

  shelter_name            TEXT NOT NULL,
  shelter_location        TEXT,
  intake_date             TEXT CHECK (intake_date IS NULL OR intake_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9]Z'),
  intake_reason           TEXT,

  -- The scheduled/threatened euthanasia date. Can move, and is cleared
  -- once the animal is no longer at risk.
  deadline_timestamp      TEXT CHECK (deadline_timestamp IS NULL OR deadline_timestamp GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9]Z'),
  status                  TEXT NOT NULL DEFAULT 'AT_RISK'
                            CHECK (status IN ('AT_RISK', 'PENDING_VERIFICATION', 'SAFE', 'ADOPTED',
                                              'TRANSFERRED', 'EUTHANIZED', 'ARCHIVED')),

  -- Set only when status becomes EUTHANIZED -- by a human, once
  -- confirmed. Never inferred from an animal dropping off a feed.
  euthanized_at           TEXT CHECK (euthanized_at IS NULL OR euthanized_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9]Z'),

  -- Local copy of the shelter photo, downloaded at first sight because
  -- the shelter's own URL can vanish. See image_archive.py.
  local_image_path        TEXT,

  -- 1 once the local copy is a permanent memorial (status EUTHANIZED);
  -- image_archive.py's cleanup will never delete it after that.
  image_permanently_archived INTEGER NOT NULL DEFAULT 0
                            CHECK (image_permanently_archived IN (0, 1)),

  -- LOCAL-ONLY: when the memorial photo was uploaded to remote, so
  -- publish.py doesn't re-upload the same bytes every run.
  remote_image_uploaded_at TEXT,

  -- Free text; also the fallback signal for fuzzy matching social posts.
  description             TEXT,

  -- The shelter's own live photo URL. Not guaranteed to stay valid.
  image_url               TEXT,

  created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

  -- Bumped automatically by the pets_bump_updated_at trigger below, and
  -- ONLY when a field that gets published actually changes. publish.py
  -- uses it to decide what to push, so bookkeeping-only updates
  -- (last_seen_in_scrape_at, local_image_path, ...) deliberately don't
  -- touch it -- otherwise every scrape would re-publish every animal.
  updated_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

  last_seen_in_scrape_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_pets_status ON pets(status);
CREATE INDEX IF NOT EXISTS idx_pets_shelter_name ON pets(shelter_name);
CREATE INDEX IF NOT EXISTS idx_pets_deadline ON pets(deadline_timestamp);
CREATE INDEX IF NOT EXISTS idx_pets_updated_at ON pets(updated_at);

CREATE TRIGGER IF NOT EXISTS pets_bump_updated_at
AFTER UPDATE ON pets
FOR EACH ROW
WHEN NEW.updated_at IS OLD.updated_at AND (
     NEW.name IS NOT OLD.name
  OR NEW.species IS NOT OLD.species
  OR NEW.breed IS NOT OLD.breed
  OR NEW.age IS NOT OLD.age
  OR NEW.sex IS NOT OLD.sex
  OR NEW.shelter_name IS NOT OLD.shelter_name
  OR NEW.shelter_location IS NOT OLD.shelter_location
  OR NEW.intake_date IS NOT OLD.intake_date
  OR NEW.intake_reason IS NOT OLD.intake_reason
  OR NEW.deadline_timestamp IS NOT OLD.deadline_timestamp
  OR NEW.status IS NOT OLD.status
  OR NEW.euthanized_at IS NOT OLD.euthanized_at
  OR NEW.description IS NOT OLD.description
  OR NEW.image_url IS NOT OLD.image_url
)
BEGIN
  UPDATE pets SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
  WHERE pet_id = NEW.pet_id;
END;

-- ------------------------------------------------------------------
-- media_sources: social media links attached to a known pet
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS media_sources (
  id          TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  pet_id      TEXT NOT NULL REFERENCES pets(pet_id) ON DELETE CASCADE,

  platform    TEXT NOT NULL,   -- 'tiktok' | 'instagram' | 'x' | 'facebook'
  url         TEXT NOT NULL,
  posted_by   TEXT,            -- the volunteer/coordinator handle
  posted_at   TEXT,
  raw_text    TEXT,            -- original caption, for audit/debug

  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

  UNIQUE (pet_id, url)
);

CREATE INDEX IF NOT EXISTS idx_media_sources_pet_id ON media_sources(pet_id);
CREATE INDEX IF NOT EXISTS idx_media_sources_created_at ON media_sources(created_at);

-- ------------------------------------------------------------------
-- pending_profiles: animals seen only in social posts, with no
-- shelter-confirmed Pet ID yet
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pending_profiles (
  id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  extracted_pet_id    TEXT,     -- may be garbled/partial
  shelter_name_guess  TEXT,
  description         TEXT,
  deadline_guess      TEXT CHECK (deadline_guess IS NULL OR deadline_guess GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9]Z'),

  platform            TEXT NOT NULL,
  url                 TEXT NOT NULL,
  posted_by           TEXT,
  raw_text            TEXT,

  -- 1 when an AI decision landed in the "uncertain" band and needs a
  -- human to confirm/reject rather than being auto-committed or discarded.
  needs_review        INTEGER NOT NULL DEFAULT 0 CHECK (needs_review IN (0, 1)),
  review_reason       TEXT,

  status              TEXT NOT NULL DEFAULT 'PENDING_VERIFICATION'
                        CHECK (status IN ('AT_RISK', 'PENDING_VERIFICATION', 'SAFE', 'ADOPTED',
                                          'TRANSFERRED', 'EUTHANIZED', 'ARCHIVED')),
  created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_pending_needs_review ON pending_profiles(needs_review);

-- ------------------------------------------------------------------
-- audit_log: one row per AI decision (extraction or fuzzy match),
-- regardless of outcome -- the accuracy/drift-detection backbone
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
  id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),

  stage           TEXT NOT NULL,   -- 'extraction' | 'fuzzy_match'
  action          TEXT NOT NULL,   -- action matching_logic.py took

  input_text      TEXT,
  model_output    TEXT,            -- raw JSON string from the model

  confidence      REAL,
  related_pet_id  TEXT,

  platform        TEXT,
  url             TEXT,

  -- Filled in once a human reviews this decision.
  human_verdict   TEXT CHECK (human_verdict IS NULL OR human_verdict IN ('correct', 'incorrect')),
  reviewed_at     TEXT,

  created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_stage ON audit_log(stage);
CREATE INDEX IF NOT EXISTS idx_audit_confidence ON audit_log(confidence);
CREATE INDEX IF NOT EXISTS idx_audit_human_verdict ON audit_log(human_verdict);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log(created_at);

-- ------------------------------------------------------------------
-- publish_state: LOCAL-ONLY single row -- when publish.py last pushed
-- successfully, so it only sends what changed since then
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS publish_state (
  id                 INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  last_published_at  TEXT
);
