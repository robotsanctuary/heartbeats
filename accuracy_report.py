"""
accuracy_report.py

Reads the audit_log and pending_profiles tables to answer two questions:

  1. "Is anything in the review queue right now?" -- the things a human
     actually needs to look at today.
  2. "Is average confidence trending down?" -- the early warning sign of
     model drift, prompt regression, or a shift in what kind of posts
     are coming through (e.g. a new volunteer with a very different
     writing style).

Run manually, or wire into a daily/weekly cron alongside the scraper
cycle.

Usage:
    python accuracy_report.py
"""

from datetime import datetime, timedelta, timezone

from db import _fmt, init_db, parse_ts, session


def print_review_queue(cur, limit: int = 20) -> None:
    rows = cur.execute(
        """
        SELECT id, extracted_pet_id, shelter_name_guess, description,
               review_reason, platform, url, created_at
        FROM pending_profiles
        WHERE needs_review = 1
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    print(f"=== Review Queue ({len(rows)} shown, most recent first) ===")
    if not rows:
        print("Nothing waiting on review. 🎉\n")
        return

    for r in rows:
        print(f"- [{parse_ts(r['created_at']):%Y-%m-%d %H:%M} UTC] id={r['id']}  {r['review_reason']}")
        print(f"    shelter: {r['shelter_name_guess']}  pet_id_guess: {r['extracted_pet_id']}")
        print(f"    desc: {r['description']}")
        print(f"    source: {r['platform']} -> {r['url']}")
    print()


def print_confidence_trend(cur, days: int = 14) -> None:
    since = _fmt(datetime.now(timezone.utc) - timedelta(days=days))
    rows = cur.execute(
        """
        SELECT
            substr(created_at, 1, 10) AS day,
            stage,
            avg(confidence) AS avg_confidence,
            count(*) AS n
        FROM audit_log
        WHERE created_at >= ? AND confidence IS NOT NULL
        GROUP BY day, stage
        ORDER BY day ASC, stage ASC
        """,
        (since,),
    ).fetchall()

    print(f"=== Daily Average Confidence, last {days} days ===")
    if not rows:
        print("No audit log entries yet in this window.\n")
        return

    for r in rows:
        print(f"  {r['day']}  {r['stage']:<13}  avg={r['avg_confidence']:.2f}  n={r['n']}")

    # Simple drift flag: compare the most recent 3 days' average against
    # the preceding period. Not statistically rigorous, but enough to
    # catch an obvious cliff.
    print()
    for stage in {r["stage"] for r in rows}:
        stage_rows = [r for r in rows if r["stage"] == stage]
        if len(stage_rows) < 4:
            continue
        recent = stage_rows[-3:]
        earlier = stage_rows[:-3]
        recent_avg = sum(r["avg_confidence"] for r in recent) / len(recent)
        earlier_avg = sum(r["avg_confidence"] for r in earlier) / len(earlier)
        if recent_avg < earlier_avg - 0.1:
            print(f"⚠️  '{stage}' confidence dropped from ~{earlier_avg:.2f} to ~{recent_avg:.2f} "
                  f"recently -- worth running test_extraction_accuracy.py to check for drift.")
    print()


def print_action_breakdown(cur, days: int = 7) -> None:
    since = _fmt(datetime.now(timezone.utc) - timedelta(days=days))
    rows = cur.execute(
        """
        SELECT action, count(*) AS n
        FROM audit_log
        WHERE created_at >= ?
        GROUP BY action
        ORDER BY n DESC
        """,
        (since,),
    ).fetchall()

    print(f"=== Action Breakdown, last {days} days ===")
    for r in rows:
        print(f"  {r['action']:<28} {r['n']}")
    print()


def print_human_verified_accuracy(cur) -> None:
    row = cur.execute(
        """
        SELECT
            sum(human_verdict = 'correct') AS correct,
            sum(human_verdict IS NOT NULL) AS reviewed
        FROM audit_log
        """
    ).fetchone()
    reviewed = row["reviewed"] or 0
    correct = row["correct"] or 0

    print("=== Human-Verified Accuracy (all time) ===")
    if reviewed == 0:
        print("No audit_log rows have been manually reviewed yet.")
        print("Set human_verdict = 'correct' / 'incorrect' on audit_log rows as you spot-check them.\n")
        return

    print(f"{correct}/{reviewed} reviewed decisions confirmed correct ({correct / reviewed:.0%})\n")


if __name__ == "__main__":
    init_db()  # no-op if the tables already exist
    with session() as cur:
        print_review_queue(cur)
        print_confidence_trend(cur)
        print_action_breakdown(cur)
        print_human_verified_accuracy(cur)
