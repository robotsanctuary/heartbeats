"""
promote_pending.py

After a human looks at accuracy_report.py's review queue and decides a
pending_profiles row is legit, this promotes it into `pets` -- making
it eligible for publish.py to push live.

This is deliberately a manual, one-row-at-a-time action, not a batch
job. Anything sitting in `pending_profiles` got there specifically
because the automated pipeline wasn't confident enough to decide on its
own -- the whole point of the review queue is a human makes the actual
call here.

Usage:
    python promote_pending.py <pending_profile_id> --pet-id A2145501 --shelter-name "Dallas Animal Services"
    python promote_pending.py <pending_profile_id> --reject
"""

import argparse
import os
import uuid

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

LOCAL_DATABASE_URL = os.environ["LOCAL_DATABASE_URL"]


def get_conn():
    return psycopg2.connect(LOCAL_DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def promote(pending_id: str, pet_id: str, shelter_name: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM pending_profiles WHERE id = %s", (pending_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"No pending_profiles row with id {pending_id}")

            # Create (or update) the real pet row.
            cur.execute(
                """
                INSERT INTO pets (pet_id, shelter_name, description, deadline_timestamp, status)
                VALUES (%s, %s, %s, %s, 'AT_RISK')
                ON CONFLICT (pet_id) DO UPDATE SET
                    description = COALESCE(pets.description, EXCLUDED.description)
                """,
                (pet_id, shelter_name, row["description"], row["deadline_guess"]),
            )

            # Carry the post over as a media source on the now-confirmed pet.
            cur.execute(
                """
                INSERT INTO media_sources (id, pet_id, platform, url, posted_by, raw_text)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (pet_id, url) DO NOTHING
                """,
                (str(uuid.uuid4()), pet_id, row["platform"], row["url"], row["posted_by"], row["raw_text"]),
            )

            # Mark the corresponding audit_log entry as human-verified correct,
            # feeding the accuracy numbers in accuracy_report.py.
            cur.execute(
                """
                UPDATE audit_log SET human_verdict = 'correct', reviewed_at = now()
                WHERE url = %s AND platform = %s AND human_verdict IS NULL
                """,
                (row["url"], row["platform"]),
            )

            cur.execute("DELETE FROM pending_profiles WHERE id = %s", (pending_id,))
        conn.commit()

    print(f"Promoted pending profile {pending_id} -> pet {pet_id}")


def reject(pending_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT platform, url FROM pending_profiles WHERE id = %s", (pending_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"No pending_profiles row with id {pending_id}")

            cur.execute(
                """
                UPDATE audit_log SET human_verdict = 'incorrect', reviewed_at = now()
                WHERE url = %s AND platform = %s AND human_verdict IS NULL
                """,
                (row["url"], row["platform"]),
            )
            cur.execute("DELETE FROM pending_profiles WHERE id = %s", (pending_id,))
        conn.commit()

    print(f"Rejected and removed pending profile {pending_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote or reject a pending_profiles row after human review.")
    parser.add_argument("pending_id", help="id column from pending_profiles")
    parser.add_argument("--pet-id", help="Confirmed official shelter pet ID to promote this into")
    parser.add_argument("--shelter-name", help="Shelter name to use on the promoted pet row")
    parser.add_argument("--reject", action="store_true", help="Reject instead of promoting")
    args = parser.parse_args()

    if args.reject:
        reject(args.pending_id)
    else:
        if not args.pet_id or not args.shelter_name:
            parser.error("--pet-id and --shelter-name are required unless using --reject")
        promote(args.pending_id, args.pet_id, args.shelter_name)
