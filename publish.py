"""
publish.py

One-way sync: LOCAL Postgres (source of truth, review happens here) ->
REMOTE Postgres (what the live website reads from).

This is the only script that talks to the remote database, and it only
ever pushes OUT to it -- nothing is ever read back from remote into
local. The remote side only ever receives `pets` and `media_sources`
rows that have already cleared review (needs_review = FALSE and not
sitting in pending_profiles). `pending_profiles` and `audit_log` --
your raw scraping data, review notes, and AI decision trail -- never
leave the local machine.

INCREMENTAL BY DEFAULT: rather than re-pushing every row on every run,
this reads a watermark (`publish_state.last_published_at`, local-only)
and only selects pets/media_sources changed since then. Status changes
(SAFE, ADOPTED, EUTHANIZED, ARCHIVED) bump `updated_at` like any other
edit, so they flow through automatically -- no special-casing needed.
Use `--full` to force a complete re-push (first run against a fresh
remote DB, or if you ever suspect remote has drifted out of sync).

Run this manually after reviewing accuracy_report.py's queue, or on a
schedule right after your scrape/matching cycle if you're comfortable
trusting the confidence-gating to have already screened out anything
risky.

Usage:
    python publish.py            # push everything changed since last run
    python publish.py --dry-run  # show what WOULD be pushed, change nothing
    python publish.py --full     # ignore the watermark, push every row

Environment:
    LOCAL_DATABASE_URL   your local Postgres (the working/review DB)
    REMOTE_DATABASE_URL  the hosted Postgres the website reads from.
                          Use a role scoped to INSERT/UPDATE on
                          `pets` and `media_sources` ONLY -- not a
                          superuser/admin connection string. That way
                          even a leaked REMOTE_DATABASE_URL can't be
                          used to touch anything beyond those two
                          tables, let alone reach your local machine.
"""

import argparse
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

LOCAL_DATABASE_URL = os.environ["LOCAL_DATABASE_URL"]
REMOTE_DATABASE_URL = os.environ["REMOTE_DATABASE_URL"]


def _utcnow():
    return datetime.now(timezone.utc)


def get_local_conn():
    return psycopg2.connect(LOCAL_DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def get_remote_conn():
    return psycopg2.connect(REMOTE_DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def get_last_published_at(local_cur):
    """
    Reads the watermark from the local-only publish_state table.
    Returns None on the very first run (no row yet), which the caller
    treats as "publish everything."
    """
    local_cur.execute("SELECT last_published_at FROM publish_state WHERE id = 1")
    row = local_cur.fetchone()
    return row["last_published_at"] if row else None


def set_last_published_at(local_cur, timestamp) -> None:
    local_cur.execute(
        """
        INSERT INTO publish_state (id, last_published_at)
        VALUES (1, %s)
        ON CONFLICT (id) DO UPDATE SET last_published_at = EXCLUDED.last_published_at
        """,
        (timestamp,),
    )


def fetch_publishable_pets(local_cur, since=None) -> list:
    """
    Everything in `pets` is, by construction, already past the review
    gate -- rows only land in `pets` via a high-confidence auto-commit
    in matching_logic.py. Genuinely uncertain finds live in
    `pending_profiles` instead and are never candidates for publishing
    until a human promotes them.

    When `since` is given, only rows updated after that watermark are
    returned -- this is what keeps publish.py from re-pushing the whole
    table every run. Status changes (SAFE, ADOPTED, EUTHANIZED,
    ARCHIVED) bump `updated_at` just like any other edit, so they're
    naturally included in the next incremental push without any special
    casing.
    """
    if since is None:
        local_cur.execute(
            """
            SELECT pet_id, name, species, breed, age, sex,
                   shelter_name, shelter_location, intake_date, intake_reason,
                   deadline_timestamp, status, euthanized_at, description, image_url,
                   local_image_path, image_permanently_archived, remote_image_uploaded_at,
                   created_at, updated_at
            FROM pets
            ORDER BY updated_at ASC
            """
        )
    else:
        local_cur.execute(
            """
            SELECT pet_id, name, species, breed, age, sex,
                   shelter_name, shelter_location, intake_date, intake_reason,
                   deadline_timestamp, status, euthanized_at, description, image_url,
                   local_image_path, image_permanently_archived, remote_image_uploaded_at,
                   created_at, updated_at
            FROM pets
            WHERE updated_at > %s
            ORDER BY updated_at ASC
            """,
            (since,),
        )
    return local_cur.fetchall()


def fetch_media_sources(local_cur, pet_ids: list, since=None) -> list:
    """
    Media sources don't have their own `updated_at` (they're
    effectively immutable once inserted), so the watermark is applied
    against `created_at` instead -- new links attached since the last
    publish. `pet_ids` further narrows this to pets we're already
    publishing in this run, though in practice the `since` filter alone
    is usually enough.
    """
    if not pet_ids:
        return []

    if since is None:
        local_cur.execute(
            """
            SELECT pet_id, platform, url, posted_by, posted_at, raw_text
            FROM media_sources
            WHERE pet_id = ANY(%s)
            """,
            (pet_ids,),
        )
    else:
        local_cur.execute(
            """
            SELECT pet_id, platform, url, posted_by, posted_at, raw_text
            FROM media_sources
            WHERE pet_id = ANY(%s) AND created_at > %s
            """,
            (pet_ids, since),
        )
    return local_cur.fetchall()


def upsert_pet(remote_cur, pet: dict) -> None:
    remote_cur.execute(
        """
        INSERT INTO pets (
            pet_id, name, species, breed, age, sex,
            shelter_name, shelter_location, intake_date, intake_reason,
            deadline_timestamp, status, euthanized_at, description, image_url, created_at, updated_at
        )
        VALUES (
            %(pet_id)s, %(name)s, %(species)s, %(breed)s, %(age)s, %(sex)s,
            %(shelter_name)s, %(shelter_location)s, %(intake_date)s, %(intake_reason)s,
            %(deadline_timestamp)s, %(status)s, %(euthanized_at)s, %(description)s, %(image_url)s, %(created_at)s, %(updated_at)s
        )
        ON CONFLICT (pet_id) DO UPDATE SET
            name = EXCLUDED.name,
            species = EXCLUDED.species,
            breed = EXCLUDED.breed,
            age = EXCLUDED.age,
            sex = EXCLUDED.sex,
            shelter_name = EXCLUDED.shelter_name,
            shelter_location = EXCLUDED.shelter_location,
            intake_date = EXCLUDED.intake_date,
            intake_reason = EXCLUDED.intake_reason,
            deadline_timestamp = EXCLUDED.deadline_timestamp,
            status = EXCLUDED.status,
            euthanized_at = EXCLUDED.euthanized_at,
            description = EXCLUDED.description,
            image_url = EXCLUDED.image_url,
            updated_at = EXCLUDED.updated_at
        """,
        pet,
    )


def upsert_media_source(remote_cur, media: dict) -> None:
    remote_cur.execute(
        """
        INSERT INTO media_sources (id, pet_id, platform, url, posted_by, posted_at, raw_text)
        VALUES (gen_random_uuid(), %(pet_id)s, %(platform)s, %(url)s, %(posted_by)s, %(posted_at)s, %(raw_text)s)
        ON CONFLICT (pet_id, url) DO NOTHING
        """,
        media,
    )


def upload_euthanized_photo(remote_cur, pet_id: str, local_image_path: str) -> str:
    """
    Reads the locally archived photo file and uploads its bytes into
    REMOTE Postgres's euthanized_photo column. This only ever runs for
    animals that are permanently archived (status == EUTHANIZED) and
    haven't been uploaded yet -- see should_upload_euthanized_photo().

    Returns a short outcome string for logging: "uploaded", "skipped_missing_file".
    """
    path = Path(local_image_path)
    if not path.exists():
        return "skipped_missing_file"

    content_type, _ = mimetypes.guess_type(str(path))
    content_type = content_type or "image/jpeg"

    remote_cur.execute(
        """
        UPDATE pets
        SET euthanized_photo = %s, euthanized_photo_content_type = %s
        WHERE pet_id = %s
        """,
        (psycopg2.Binary(path.read_bytes()), content_type, pet_id),
    )
    return "uploaded"


def should_upload_euthanized_photo(pet: dict) -> bool:
    return bool(
        pet.get("status") == "EUTHANIZED"
        and pet.get("image_permanently_archived")
        and pet.get("local_image_path")
        and not pet.get("remote_image_uploaded_at")
    )


def publish(dry_run: bool = False, full: bool = False) -> dict:
    """
    `full=True` forces a full re-push of every row, ignoring the
    watermark -- useful for a first-ever run against a fresh remote
    database, or to recover if you ever suspect remote has drifted out
    of sync with local.
    """
    with get_local_conn() as local_conn:
        with local_conn.cursor() as local_cur:
            since = None if full else get_last_published_at(local_cur)

            # Captured BEFORE the fetch, not after -- so anything updated
            # while this run is in flight gets picked up on the *next*
            # run rather than silently skipped.
            run_started_at = _utcnow()

            pets = fetch_publishable_pets(local_cur, since=since)
            pet_ids = [p["pet_id"] for p in pets]
            media_sources = fetch_media_sources(local_cur, pet_ids, since=since)

    photos_to_upload = [p for p in pets if should_upload_euthanized_photo(p)]

    if dry_run:
        mode = "FULL" if since is None else f"since {since}"
        print(f"[DRY RUN, {mode}] Would publish {len(pets)} pets and {len(media_sources)} media sources.")
        print(f"[DRY RUN] Would upload {len(photos_to_upload)} euthanized memorial photo(s).")
        for p in pets:
            marker = " [+ photo upload]" if p in photos_to_upload else ""
            print(f"  {p['pet_id']:<12} {p['status']:<12} {p['name']}{marker}")
        return {"pets": len(pets), "media_sources": len(media_sources), "photos": len(photos_to_upload), "dry_run": True}

    if not pets and not media_sources:
        print("Nothing new to publish since last run.")
        return {"pets": 0, "media_sources": 0, "photos": 0, "dry_run": False}

    # Push happens on the remote connection first; only if it succeeds
    # do we advance the local watermark. If the remote push fails, the
    # watermark stays put and the same delta will simply be retried
    # (safely -- these are upserts) on the next run.
    photo_results = {"uploaded": 0, "skipped_missing_file": 0}

    with get_remote_conn() as remote_conn:
        with remote_conn.cursor() as remote_cur:
            for pet in pets:
                upsert_pet(remote_cur, pet)
            for media in media_sources:
                upsert_media_source(remote_cur, media)
            for pet in photos_to_upload:
                result = upload_euthanized_photo(remote_cur, pet["pet_id"], pet["local_image_path"])
                photo_results[result] = photo_results.get(result, 0) + 1
        remote_conn.commit()

    with get_local_conn() as local_conn:
        with local_conn.cursor() as local_cur:
            set_last_published_at(local_cur, run_started_at)
            # Mark successfully uploaded photos so future runs don't
            # re-upload the same bytes.
            uploaded_ids = [
                p["pet_id"] for p in photos_to_upload
                if Path(p["local_image_path"]).exists()
            ]
            if uploaded_ids:
                local_cur.execute(
                    "UPDATE pets SET remote_image_uploaded_at = %s WHERE pet_id = ANY(%s)",
                    (run_started_at, uploaded_ids),
                )
        local_conn.commit()

    print(f"Published {len(pets)} pets and {len(media_sources)} media sources to remote. "
          f"Uploaded {photo_results['uploaded']} memorial photo(s) "
          f"({photo_results['skipped_missing_file']} skipped -- local file missing). "
          f"Watermark advanced to {run_started_at}.")
    return {"pets": len(pets), "media_sources": len(media_sources), "photos": photo_results["uploaded"], "dry_run": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Push vetted local data to the remote/production database.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be published without writing anything.")
    parser.add_argument("--full", action="store_true", help="Ignore the watermark and re-push every row (e.g. first run, or recovering from suspected drift).")
    args = parser.parse_args()

    publish(dry_run=args.dry_run, full=args.full)
