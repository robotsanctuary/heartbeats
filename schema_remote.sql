-- schema_remote.sql
-- Apply this to the REMOTE database instead of the full schema.sql.
-- It's deliberately a subset: the remote DB only ever needs to serve
-- the website, so it only gets `pets` and `media_sources` -- no
-- pending_profiles, audit_log, or publish_state. Those exist only
-- locally, by design (see README section on architecture).
--
-- Run with:
--   psql "$REMOTE_DATABASE_URL" -f schema_remote.sql

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
  euthanized_at           TIMESTAMPTZ,

  -- The permanent memorial photo, uploaded by publish.py only once,
  -- only for animals whose status is EUTHANIZED. Ordinary at-risk
  -- animals are represented by their shelter's own image_url (not
  -- stored here) -- this column exists specifically so the photo
  -- survives even if the shelter's own URL later goes dead.
  euthanized_photo             BYTEA,
  euthanized_photo_content_type TEXT,

  description             TEXT,

  -- The shelter's own live photo URL, for currently at-risk/adoptable
  -- animals -- this is what the website uses for everyone who is NOT
  -- (yet) euthanized. Not guaranteed to stay valid forever; that's what
  -- euthanized_photo above is for, once it applies.
  image_url               TEXT,

  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_pets_status ON pets(status);
CREATE INDEX idx_pets_shelter_name ON pets(shelter_name);
CREATE INDEX idx_pets_deadline ON pets(deadline_timestamp);

CREATE TABLE media_sources (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pet_id      TEXT NOT NULL REFERENCES pets(pet_id) ON DELETE CASCADE,

  platform    TEXT NOT NULL,
  url         TEXT NOT NULL,
  posted_by   TEXT,
  posted_at   TIMESTAMPTZ,
  raw_text    TEXT,

  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (pet_id, url)
);

CREATE INDEX idx_media_sources_pet_id ON media_sources(pet_id);

-- ============================================================
-- Public-facing submissions. Unlike everything above, these are
-- NEVER pushed from local -- they're born here, written directly by
-- the live website's public-facing forms. They sit in PENDING status
-- until a moderator (manual today, AI-assisted later -- see
-- ai_review_notes) approves or rejects them. Nothing here is ever
-- shown publicly while status = PENDING.
-- ============================================================

CREATE TYPE moderation_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED');

CREATE TABLE comments (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pet_id          TEXT NOT NULL REFERENCES pets(pet_id) ON DELETE CASCADE,
  author_name     TEXT,       -- optional; no account system required initially
  body            TEXT NOT NULL,

  status          moderation_status NOT NULL DEFAULT 'PENDING',

  -- Filled in once AI-assisted moderation exists (run locally on the
  -- Mac mini, connecting outbound to review PENDING rows). Kept as a
  -- plain text field now so that feature can slot in later without a
  -- schema change -- a short verdict/reasoning string, not a score.
  ai_review_notes TEXT,

  -- A hash, not the raw IP -- enough for basic spam/rate-limit
  -- tracking without holding onto visitor PII unnecessarily.
  ip_hash         TEXT,

  submitted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  moderated_at    TIMESTAMPTZ
);

CREATE INDEX idx_comments_pet_id ON comments(pet_id);
CREATE INDEX idx_comments_status ON comments(status);

CREATE TABLE submitted_media (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pet_id          TEXT NOT NULL REFERENCES pets(pet_id) ON DELETE CASCADE,

  platform        TEXT NOT NULL,   -- 'tiktok' | 'instagram' | 'facebook' | 'x'
  url             TEXT NOT NULL,
  submitted_by    TEXT,
  note            TEXT,            -- optional context the submitter adds

  status          moderation_status NOT NULL DEFAULT 'PENDING',
  ai_review_notes TEXT,
  ip_hash         TEXT,

  submitted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  moderated_at    TIMESTAMPTZ
);

CREATE INDEX idx_submitted_media_pet_id ON submitted_media(pet_id);
CREATE INDEX idx_submitted_media_status ON submitted_media(status);

-- After running this, create these roles on the remote DB:
--   1. A "publisher" role with INSERT/UPDATE on pets + media_sources
--      only -- this is what REMOTE_DATABASE_URL in .env should use.
--   2. A "reader" role with SELECT only on pets, media_sources,
--      comments (APPROVED only, enforce via a view -- see below), and
--      submitted_media (APPROVED only, same) -- this is what the
--      website's read path uses.
--   3. A "public_submitter" role with INSERT ONLY on comments and
--      submitted_media -- nothing else, not even SELECT. This is what
--      the website's public comment/submission forms use. Scoped this
--      tightly, a leaked credential here can only ever create new
--      PENDING rows, never read, modify, or delete anything.
--   4. A "moderator" role with SELECT/UPDATE on comments and
--      submitted_media, plus INSERT on media_sources (to promote an
--      approved submission into the real table). This is what
--      moderate.py uses -- keep this credential local only (Mac mini),
--      never given to the website.
--
-- Example (adjust for your host's exact role-management UI/SQL):
--   CREATE ROLE publisher LOGIN PASSWORD '...';
--   GRANT INSERT, UPDATE, SELECT ON pets, media_sources TO publisher;
--
--   CREATE ROLE reader LOGIN PASSWORD '...';
--   GRANT SELECT ON pets, media_sources TO reader;
--   GRANT SELECT ON approved_comments, approved_submitted_media TO reader;
--
--   CREATE ROLE public_submitter LOGIN PASSWORD '...';
--   GRANT INSERT ON comments, submitted_media TO public_submitter;
--
--   CREATE ROLE moderator LOGIN PASSWORD '...';
--   GRANT SELECT, UPDATE ON comments, submitted_media TO moderator;
--   GRANT INSERT ON media_sources TO moderator;
--
-- The "reader" role should never see PENDING/REJECTED comments or
-- submissions -- rather than trusting every query in the website's
-- code to remember a WHERE status = 'APPROVED' clause, enforce it at
-- the database level with views the reader role queries instead of
-- the raw tables:
--
--   CREATE VIEW approved_comments AS
--     SELECT id, pet_id, author_name, body, submitted_at
--     FROM comments WHERE status = 'APPROVED';
--
--   CREATE VIEW approved_submitted_media AS
--     SELECT id, pet_id, platform, url, note, submitted_at
--     FROM submitted_media WHERE status = 'APPROVED';
