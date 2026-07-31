"""
moderate.py

Manual moderation for the two kinds of public-submitted content:
comments on animal pages, and user-submitted social media links.
Both start life as PENDING and are invisible on the live site until
approved here.

THIS IS THE MANUAL VERSION. The plan is to eventually add AI-assisted
moderation (likely a local model on the Mac mini, same cost reasoning
as the rest of this project) that pre-screens PENDING rows and either
auto-approves/auto-rejects clear cases or leaves genuinely ambiguous
ones PENDING for a human -- the same confidence-gating pattern already
used in matching_logic.py. That script would write to the same
`status` and `ai_review_notes` columns this one does, so nothing here
needs to change when it's built -- it just becomes a second way rows
get moderated, alongside this manual tool.

Usage:
    python moderate.py queue                       # show everything PENDING
    python moderate.py approve comment <id>
    python moderate.py reject  comment <id> --reason "spam"
    python moderate.py approve media <id>           # also promotes into media_sources
    python moderate.py reject  media <id> --reason "unrelated animal"

Environment:
    MODERATOR_DATABASE_URL   the "moderator" role's connection string
                              (see schema_remote.sql for the role
                              definition). Keep this local only --
                              never give it to the website.
"""

import argparse
import os
import uuid

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

MODERATOR_DATABASE_URL = os.environ["MODERATOR_DATABASE_URL"]


def get_conn():
    return psycopg2.connect(MODERATOR_DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def show_queue():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, pet_id, author_name, body, submitted_at
                FROM comments WHERE status = 'PENDING'
                ORDER BY submitted_at ASC
                """
            )
            comments = cur.fetchall()

            cur.execute(
                """
                SELECT id, pet_id, platform, url, note, submitted_by, submitted_at
                FROM submitted_media WHERE status = 'PENDING'
                ORDER BY submitted_at ASC
                """
            )
            media = cur.fetchall()

    print(f"=== Pending comments ({len(comments)}) ===")
    for c in comments:
        print(f"  [{c['id']}] on {c['pet_id']} by {c['author_name'] or 'anonymous'} at {c['submitted_at']:%Y-%m-%d %H:%M}")
        print(f"      {c['body']!r}")
    if not comments:
        print("  (none)")
    print()

    print(f"=== Pending media submissions ({len(media)}) ===")
    for m in media:
        print(f"  [{m['id']}] on {m['pet_id']} -- {m['platform']}: {m['url']}")
        if m["note"]:
            print(f"      note: {m['note']!r}")
    if not media:
        print("  (none)")
    print()


def approve_comment(comment_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE comments SET status = 'APPROVED', moderated_at = now() WHERE id = %s",
                (comment_id,),
            )
        conn.commit()
    print(f"Approved comment {comment_id}")


def reject_comment(comment_id: str, reason: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE comments SET status = 'REJECTED', moderated_at = now(), ai_review_notes = %s WHERE id = %s",
                (reason, comment_id),
            )
        conn.commit()
    print(f"Rejected comment {comment_id}: {reason}")


def approve_media(submission_id: str):
    """
    Approving a media submission both flips its status AND promotes it
    into the real media_sources table -- that's the table animal pages
    actually render from, same one publish.py writes to. Comments have
    no equivalent "promotion" step since the comments table itself is
    what gets displayed.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM submitted_media WHERE id = %s", (submission_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"No submitted_media row with id {submission_id}")

            cur.execute(
                """
                INSERT INTO media_sources (id, pet_id, platform, url, posted_by, raw_text)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (pet_id, url) DO NOTHING
                """,
                (str(uuid.uuid4()), row["pet_id"], row["platform"], row["url"], row["submitted_by"], row["note"]),
            )
            cur.execute(
                "UPDATE submitted_media SET status = 'APPROVED', moderated_at = now() WHERE id = %s",
                (submission_id,),
            )
        conn.commit()
    print(f"Approved and promoted media submission {submission_id} -> media_sources")


def reject_media(submission_id: str, reason: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE submitted_media SET status = 'REJECTED', moderated_at = now(), ai_review_notes = %s WHERE id = %s",
                (reason, submission_id),
            )
        conn.commit()
    print(f"Rejected media submission {submission_id}: {reason}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Moderate pending comments and social media submissions.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("queue", help="Show everything pending review")

    approve_p = sub.add_parser("approve", help="Approve a comment or media submission")
    approve_p.add_argument("kind", choices=["comment", "media"])
    approve_p.add_argument("id")

    reject_p = sub.add_parser("reject", help="Reject a comment or media submission")
    reject_p.add_argument("kind", choices=["comment", "media"])
    reject_p.add_argument("id")
    reject_p.add_argument("--reason", default="", help="Short reason, stored for audit purposes")

    args = parser.parse_args()

    if args.command == "queue":
        show_queue()
    elif args.command == "approve":
        (approve_comment if args.kind == "comment" else approve_media)(args.id)
    elif args.command == "reject":
        (reject_comment if args.kind == "comment" else reject_media)(args.id, args.reason)
