"""
run_scheduled.py

Entry point for the scheduled job (Hermes cron, 9am / 3pm / 9pm).

Each run:
  1. Runs every shelter scraper with --write.
  2. Appends one line to the run log (RUN_LOG_PATH, JSON lines), success
     or failure, so a run that silently stopped happening is noticeable.
  3. Prints NOTHING on a normal run -- the scheduler only sends a
     Telegram message when there's output.
  4. Prints a failure alert if a scraper failed.
  5. With --summary, prints the daily summary (sent after the 9pm run).

Usage:
    python run_scheduled.py              # scrape quietly
    python run_scheduled.py --summary    # scrape, then print the daily summary
    python run_scheduled.py --summary-only
"""

import argparse
import contextlib
import io
import json
import os
import re
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import db

LOCAL_TZ = ZoneInfo("America/Chicago")
EXPECTED_RUNS_PER_DAY = 3


def run_log_path() -> Path:
    p = Path(os.environ.get("RUN_LOG_PATH") or "data/runs.jsonl").expanduser()
    return p if p.is_absolute() else db.REPO_DIR / p


def _scrapers():
    from shelters.texas import dallas
    return [("Dallas", dallas.run)]


def run_all() -> list:
    records = []
    for name, fn in _scrapers():
        buf = io.StringIO()
        rec = {"at": db.utcnow(), "shelter": name}
        try:
            with contextlib.redirect_stdout(buf):
                rec["result"] = fn(write=True)
            rec["ok"] = True
        except Exception as e:
            rec["ok"] = False
            rec["error"] = f"{type(e).__name__}: {e}"
            rec["trace"] = traceback.format_exc()[-1500:]
        rec["warnings"] = [l.strip() for l in buf.getvalue().splitlines() if "⚠️" in l]
        records.append(rec)

    path = run_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return records


def read_runs(since: datetime) -> list:
    path = run_log_path()
    if not path.exists():
        return []
    cutoff = db._fmt(since)
    out = []
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("at", "") >= cutoff:
            out.append(r)
    return out


def failure_alert(records: list) -> str:
    bad = [r for r in records if not r["ok"]]
    if not bad:
        return ""
    lines = ["⚠️ Heartbeats scrape FAILED"]
    for r in bad:
        lines.append(f"• {r['shelter']}: {r['error'][:300]}")
    lines.append("Data from the previous run is unchanged. Next run will retry.")
    return "\n".join(lines)


def build_summary(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=24)
    since_s = db._fmt(since)
    local_today = now.astimezone(LOCAL_TZ).date()
    # Deadlines today/tomorrow in Dallas time -> UTC window
    start = datetime.combine(local_today, datetime.min.time(), LOCAL_TZ)
    end = start + timedelta(days=2)

    with db.session() as c:
        def one(sql, *a):
            return c.execute(sql, a).fetchone()["n"]

        at_risk = one("SELECT count(*) n FROM pets WHERE status='AT_RISK'")
        with_deadline = one("SELECT count(*) n FROM pets WHERE status='AT_RISK' AND deadline_timestamp IS NOT NULL")
        new = one("SELECT count(*) n FROM pets WHERE created_at >= ?", since_s)
        urgent = c.execute(
            """SELECT pet_id, name, species, deadline_timestamp FROM pets
               WHERE status='AT_RISK' AND deadline_timestamp >= ? AND deadline_timestamp < ?
               ORDER BY deadline_timestamp, pet_id""",
            (db._fmt(start), db._fmt(end)),
        ).fetchall()
        overdue = one(
            "SELECT count(*) n FROM pets WHERE status='AT_RISK' AND deadline_timestamp < ?",
            db._fmt(start),
        )
        outcomes = {r["status"]: r["n"] for r in c.execute(
            """SELECT status, count(*) n FROM pets
               WHERE updated_at >= ? AND created_at < ?
                 AND status IN ('ADOPTED','TRANSFERRED','SAFE','ARCHIVED','PENDING_VERIFICATION')
               GROUP BY status""", (since_s, since_s)).fetchall()}

    runs = read_runs(since)
    ok_runs = [r for r in runs if r.get("ok")]
    failed = [r for r in runs if not r.get("ok")]
    warnings = sorted({w for r in runs for w in r.get("warnings", []) if "Unrecognized" in w or "0 animals" in w})
    image_fail = sum((r.get("result") or {}).get("image_failures", 0) for r in ok_runs)

    L = [f"🐾 Heartbeats daily — {local_today:%a %b %-d}", ""]
    L.append(f"Dallas: {at_risk} at risk ({with_deadline} with a deadline), +{new} new in 24h")
    if urgent:
        L.append(f"⏰ {len(urgent)} deadline today/tomorrow:")
        for p in urgent[:10]:
            d = db.parse_ts(p["deadline_timestamp"]).astimezone(LOCAL_TZ).date()
            when = "today" if d == local_today else "tomorrow"
            L.append(f"   • {p['name'] or '(no name)'} {p['pet_id']} ({p['species'].lower()}) — {when}")
        if len(urgent) > 10:
            L.append(f"   …and {len(urgent) - 10} more")
    else:
        L.append("⏰ No deadlines today/tomorrow")
    if overdue:
        L.append(f"❗ {overdue} still listed past their deadline")
    out_bits = [f"{outcomes[k]} {label}" for k, label in
                [("ADOPTED", "adopted"), ("TRANSFERRED", "transferred"), ("SAFE", "safe/foster/RTO")] if outcomes.get(k)]
    L.append("✅ Out: " + (", ".join(out_bits) if out_bits else "none in 24h"))
    if outcomes.get("ARCHIVED"):
        L.append(f"❓ {outcomes['ARCHIVED']} dropped off the feed, outcome unknown")
    if outcomes.get("PENDING_VERIFICATION"):
        L.append(f"🔎 {outcomes['PENDING_VERIFICATION']} need a manual check (new outcome type)")
    L.append("")
    run_line = f"Runs (24h): {len(ok_runs)} ok"
    if failed:
        run_line += f", {len(failed)} FAILED"
    if len(runs) < EXPECTED_RUNS_PER_DAY:
        run_line += f" — expected {EXPECTED_RUNS_PER_DAY}, some runs didn't happen"
    L.append(run_line)
    if image_fail:
        L.append(f"Photo download failures: {image_fail}")
    for w in warnings:
        L.append(w)
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args()

    db.init_db()
    parts = []
    if not args.summary_only:
        alert = failure_alert(run_all())
        if alert:
            parts.append(alert)
    if args.summary or args.summary_only:
        parts.append(build_summary())
    if parts:
        print("\n\n".join(parts))
