-- schema.sql
-- Raw SQL equivalent of schema.prisma, if you'd rather run this directly
-- against Postgres instead of using the Prisma CLI.
--
-- Run with:
--   psql "$DATABASE_URL" -f schema.sql

CREATE TYPE pet_status AS ENUM (
  'AT_RISK', 'PENDING_VERIFICATION', 'SAFE', 'ADOPTED',
  'TRANSFERRED', 'EUTHANIZED', 'ARCHIVED'
);

CREATE TYPE species AS ENUM ('DOG', 'CAT', 'OTHER');

CREATE TABLE pets (
  pet_id                  TEXT PRIMARY KEY,
  name                    TEXT,
  species                 species NOT NULL DEFAULT 'DOG',
  breed                   TEXT,
  age                     TEXT,
  sex                     TEXT,

  shelter_name            TEXT NOT NULL,
  shelter_location        TEXT,
  intake_date             TIMESTAMPTZ,
  intake_reason           TEXT,

  deadline_timestamp      TIMESTAMPTZ,
  status                  pet_status NOT NULL DEFAULT 'AT_RISK',

  -- Set only when status transitions to EUTHANIZED. Distinct from
  -- deadline_timestamp (the scheduled/threatened date) -- this is the
  -- confirmed actual outcome date, once known, for the euthanized page.
  euthanized_at           TIMESTAMPTZ,

  -- Path to a LOCALLY downloaded copy of the shelter's photo, on the
  -- external SSD. Downloaded as soon as the animal is first ingested
  -- as AT_RISK -- not waited on -- because the shelter's own image URL
  -- can vanish once the animal's record drops off their feed. See
  -- image_archive.py.
  local_image_path        TEXT,

  -- True once the local copy has been promoted to a permanent memorial
  -- (status became EUTHANIZED) rather than a temporary working copy
  -- that gets deleted once the animal is resolved. Once true,
  -- image_archive.py's cleanup step will never delete this file.
  image_permanently_archived BOOLEAN NOT NULL DEFAULT FALSE,

  -- LOCAL-ONLY tracking of whether the permanent memorial photo has
  -- already been uploaded to REMOTE Postgres (see publish.py). Prevents
  -- re-uploading the same bytes on every incremental publish run just
  -- because some other field on the pet changed.
  remote_image_uploaded_at TIMESTAMPTZ,

  description             TEXT,

  -- The shelter's own live photo URL, for currently at-risk/adoptable
  -- animals. Not guaranteed to stay valid once the animal's record
  -- leaves the shelter's feed -- see local_image_path / euthanized_photo
  -- (remote) for the durable copies.
  image_url               TEXT,

  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_in_scrape_at  TIMESTAMPTZ
);

CREATE INDEX idx_pets_status ON pets(status);
CREATE INDEX idx_pets_shelter_name ON pets(shelter_name);
CREATE INDEX idx_pets_deadline ON pets(deadline_timestamp);

CREATE TABLE media_sources (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pet_id      TEXT NOT NULL REFERENCES pets(pet_id) ON DELETE CASCADE,

  platform    TEXT NOT NULL,   -- 'tiktok' | 'instagram' | 'x' | 'facebook'
  url         TEXT NOT NULL,
  posted_by   TEXT,
  posted_at   TIMESTAMPTZ,
  raw_text    TEXT,

  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (pet_id, url)
);

CREATE INDEX idx_media_sources_pet_id ON media_sources(pet_id);

CREATE TABLE pending_profiles (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  extracted_pet_id    TEXT,
  shelter_name_guess  TEXT,
  description         TEXT,
  deadline_guess      TIMESTAMPTZ,

  platform            TEXT NOT NULL,
  url                 TEXT NOT NULL,
  posted_by           TEXT,
  raw_text            TEXT,

  -- True when an AI decision landed in the "uncertain" band and needs a
  -- human to confirm/reject rather than being auto-committed or discarded.
  needs_review        BOOLEAN NOT NULL DEFAULT FALSE,
  review_reason       TEXT,

  status              pet_status NOT NULL DEFAULT 'PENDING_VERIFICATION',
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_pending_needs_review ON pending_profiles(needs_review);

-- One row per AI decision point (extraction or fuzzy match), regardless of
-- outcome. This is the accuracy/drift-detection backbone: track confidence
-- trends over time and spot-check what the model got wrong.
CREATE TABLE audit_log (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  stage           TEXT NOT NULL,   -- 'extraction' | 'fuzzy_match'
  action          TEXT NOT NULL,   -- action matching_logic.py took

  input_text      TEXT,
  model_output    TEXT,            -- raw JSON string from the model

  confidence      DOUBLE PRECISION,
  related_pet_id  TEXT,

  platform        TEXT,
  url             TEXT,

  -- Filled in later once a human reviews this decision.
  human_verdict   TEXT,            -- 'correct' | 'incorrect' | NULL (unreviewed)
  reviewed_at     TIMESTAMPTZ,

  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_stage ON audit_log(stage);
CREATE INDEX idx_audit_confidence ON audit_log(confidence);
CREATE INDEX idx_audit_human_verdict ON audit_log(human_verdict);

-- LOCAL-ONLY. Single-row table tracking the last time publish.py
-- successfully pushed to the remote database, so it can select only
-- what changed since then instead of re-pushing everything. Not
-- needed on the remote schema at all.
CREATE TABLE publish_state (
  id                 INT PRIMARY KEY DEFAULT 1,
  last_published_at  TIMESTAMPTZ,
  CONSTRAINT single_row CHECK (id = 1)
);

-- Requires the pgcrypto extension for gen_random_uuid():
-- CREATE EXTENSION IF NOT EXISTS pgcrypto;
