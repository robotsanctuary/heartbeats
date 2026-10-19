"""
shelters/common.py

Shared helpers for all shelter scraper scripts. Each shelter/state
script (e.g. shelters/texas/dallas.py) should import from here rather
than reimplementing HTML stripping, DB writes, etc. Keep this file
generic -- anything specific to one shelter's feed quirks belongs in
that shelter's own file, not here.

All DB helpers take a sqlite3 connection from db.session() (the local
SQLite database) and leave committing to the caller.
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from db import _fmt, utcnow

USER_AGENT = "heartbeats-shelter-aggregator/0.1 (+https://github.com/robotsanctuary/heartbeats)"

PET_COLUMNS = [
    "pet_id", "name", "species", "breed", "age", "sex",
    "shelter_name", "shelter_location", "intake_date", "intake_reason",
    "deadline_timestamp", "status", "description", "image_url",
]


def strip_html(text: Optional[str]) -> Optional[str]:
    """Collapse raw HTML tags/whitespace in shelter-provided description text."""
    if not text:
        return text
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def fetch_bytes(url: str, timeout: int = 30) -> bytes:
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.content


def parse_xml(content: bytes):
    return ET.fromstring(content)


def fetch_xml(url: str, timeout: int = 30):
    return parse_xml(fetch_bytes(url, timeout))


def check_unknown_categories(values_seen: set, known_values: set, label: str) -> set:
    """
    Every shelter feed eventually introduces a category value nobody's
    seen before (a new Pathway, a new KennelStatus, etc.). Rather than
    silently ignoring unrecognized values -- which is how animals
    quietly fall through the cracks -- every shelter script should call
    this after normalizing a batch, and print/log anything unexpected
    so a human notices and updates the mapping.

    Returns the set of genuinely new (unrecognized) values.
    """
    unknown = values_seen - known_values
    if unknown:
        print(f"⚠️  Unrecognized {label} value(s), not yet mapped: {unknown}")
    return unknown


def upsert_pet_local(conn, pet: dict) -> str:
    """
    Writes one normalized pet dict into the LOCAL `pets` table. Official
    shelter feeds hand us a clean pet_id, so this is a plain upsert --
    no AI matching needed.

    updated_at is NOT set here: the schema's trigger bumps it only when
    a published field actually changed, so re-scraping an unchanged
    animal doesn't make publish.py re-send it.

    Returns "inserted", "updated" (a published field changed) or
    "unchanged".
    """
    if not pet.get("pet_id") or not pet.get("shelter_name"):
        raise ValueError(f"pet_id and shelter_name are required, got {pet.get('pet_id')!r}/{pet.get('shelter_name')!r}")

    values = {c: pet.get(c) for c in PET_COLUMNS}
    before = conn.execute(
        f"SELECT {', '.join(PET_COLUMNS)} FROM pets WHERE pet_id = ?", (values["pet_id"],)
    ).fetchone()

    conn.execute(
        f"""
        INSERT INTO pets ({', '.join(PET_COLUMNS)})
        VALUES ({', '.join(':' + c for c in PET_COLUMNS)})
        ON CONFLICT (pet_id) DO UPDATE SET
            {', '.join(f"{c} = excluded.{c}" for c in PET_COLUMNS if c != 'pet_id')}
        """,
        values,
    )
    if before is None:
        return "inserted"
    # Compare field values (not updated_at, which only has millisecond
    # resolution and could miss a change made within the same ms).
    return "updated" if any(before[c] != values[c] for c in PET_COLUMNS) else "unchanged"


def touch_last_seen(conn, pet_ids: list, seen_at: Optional[str] = None) -> None:
    """
    Marks these pet_ids as seen in this scrape cycle. Combined with
    mark_missing_as_resolved(), this is how a scraper detects an animal
    dropping off a shelter's feed without the shelter telling us why.
    """
    if not pet_ids:
        return
    seen_at = seen_at or utcnow()
    conn.executemany(
        "UPDATE pets SET last_seen_in_scrape_at = ? WHERE pet_id = ?",
        [(seen_at, pid) for pid in pet_ids],
    )


def mark_missing_as_resolved(conn, shelter_name: str, seen_pet_ids: list, grace_period_hours: int = 12) -> list:
    """
    Any AT_RISK pet from this shelter that wasn't in this scrape's
    results, and hasn't been seen in over `grace_period_hours`, gets
    ARCHIVED. This does NOT mark them EUTHANIZED -- that needs actual
    confirmation, not an inference from "they disappeared." ARCHIVED
    means "no longer on this shelter's feed, outcome unknown."

    Safety: if this scrape saw ZERO animals, nothing is archived. An
    empty result is far more likely a broken/empty feed than every
    animal leaving at once, and archiving on it would wipe the list.

    Returns the list of pet_ids that were archived.
    """
    if not seen_pet_ids:
        print(f"⚠️  [{shelter_name}] Scrape returned 0 animals -- skipping archive step (likely a feed problem).")
        return []

    cutoff = _fmt(datetime.now(timezone.utc) - timedelta(hours=int(grace_period_hours)))
    seen = set(seen_pet_ids)
    candidates = conn.execute(
        """
        SELECT pet_id FROM pets
        WHERE shelter_name = ?
          AND status = 'AT_RISK'
          AND (last_seen_in_scrape_at IS NULL OR last_seen_in_scrape_at < ?)
        """,
        (shelter_name, cutoff),
    ).fetchall()
    to_archive = [r["pet_id"] for r in candidates if r["pet_id"] not in seen]
    conn.executemany(
        "UPDATE pets SET status = 'ARCHIVED' WHERE pet_id = ?",
        [(pid,) for pid in to_archive],
    )
    return to_archive
