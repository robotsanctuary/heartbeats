-- example_queries.sql
--
-- These run against REMOTE Postgres (what the website reads from),
-- using the website's read-only role. They're examples for whatever
-- frontend you build in Phase 3, showing exactly how the three views
-- you asked for map onto the existing schema.
--
-- Three date fields drive all of this:
--   intake_date         when the animal entered the shelter
--   deadline_timestamp  the scheduled/threatened euthanasia date (may be
--                        updated or cleared as circumstances change)
--   euthanized_at        set only once, when status actually becomes
--                        EUTHANIZED -- the confirmed outcome date

-- ============================================================
-- 1. UPCOMING: animals with a future deadline, soonest first
-- ============================================================
SELECT pet_id, name, breed, shelter_name, deadline_timestamp, status
FROM pets
WHERE status = 'AT_RISK'
  AND deadline_timestamp > now()
ORDER BY deadline_timestamp ASC;

-- ============================================================
-- 2. TODAY: animals whose deadline falls today
--    (this is the "may be euthanized today" list)
-- ============================================================
SELECT pet_id, name, breed, shelter_name, deadline_timestamp, status
FROM pets
WHERE status = 'AT_RISK'
  AND deadline_timestamp::date = (now() AT TIME ZONE 'UTC')::date
ORDER BY deadline_timestamp ASC;

-- Note on timezones: shelters report deadlines in local time, but
-- deadline_timestamp is stored as TIMESTAMPTZ (UTC internally). If a
-- shelter's "today" should mean *their* local day rather than UTC,
-- swap 'UTC' above for the shelter's actual timezone, e.g.:
--   (now() AT TIME ZONE 'America/Chicago')::date
-- and compare against deadline_timestamp AT TIME ZONE 'America/Chicago'.
-- Worth deciding deliberately once Script A is pulling from multiple
-- shelters in different timezones.

-- ============================================================
-- 3. EUTHANIZED PAGE: confirmed outcomes, most recent first
-- ============================================================
SELECT pet_id, name, breed, shelter_name, euthanized_at, deadline_timestamp
FROM pets
WHERE status = 'EUTHANIZED'
ORDER BY euthanized_at DESC;

-- Optional: euthanized this week / this month, for a summary stat
SELECT count(*) AS euthanized_this_week
FROM pets
WHERE status = 'EUTHANIZED'
  AND euthanized_at >= now() - interval '7 days';

-- ============================================================
-- Bonus: a single "status of the day" query, useful for a homepage
-- summary bar (X at risk today, Y saved this week, Z lost this week)
-- ============================================================
SELECT
  count(*) FILTER (WHERE status = 'AT_RISK' AND deadline_timestamp::date = current_date) AS at_risk_today,
  count(*) FILTER (WHERE status IN ('SAFE', 'ADOPTED', 'TRANSFERRED') AND updated_at >= now() - interval '7 days') AS saved_this_week,
  count(*) FILTER (WHERE status = 'EUTHANIZED' AND euthanized_at >= now() - interval '7 days') AS euthanized_this_week
FROM pets;
