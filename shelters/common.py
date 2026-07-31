"""
shelters/common.py

Shared helpers for all shelter scraper scripts. Each shelter/state
script (e.g. shelters/texas/dallas.py) should import from here rather
than reimplementing HTML stripping, DB writes, etc. Keep this file
generic -- anything specific to one shelter's feed quirks belongs in
that shelter's own file, not here.
"""

import os
import re
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

load_dotenv()

LOCAL_DATABASE_URL = os.environ.get("LOCAL_DATABASE_URL")  # optional -- scripts can run in print-only mode without it


def get_local_conn():
    if not LOCAL_DATABASE_URL:
        raise RuntimeError("LOCAL_DATABASE_URL is not set -- can't write to the database. Run in print-only/dry-run mode instead.")
    return psycopg2.connect(LOCAL_DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def strip_html(text: Optional[str]) -> Optional[str]:
    """Collapse raw HTML tags/whitespace in shelter-provided description text."""
    if not text:
        return text
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def fetch_xml(url: str, timeout: int = 30):
    import xml.etree.ElementTree as ET
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return ET.fromstring(resp.content)


def check_unknown_categories(values_seen: set, known_values: set, label: str) -> set:
    """
    Every shelter feed eventually introduces a category value nobody's
    seen before (a new Pathway, a new KennelStatus, etc.). Rather than
    silently ignoring unrecognized values -- which is how animals
    quietly fall through the cracks -- every shelter script should call
    this after normalizing a batch, and print/log anything unexpected
    so a human notices and updates the mapping, instead of finding out
    only when someone asks "why wasn't this animal on the list?"

    Returns the set of genuinely new (unrecognized) values.
    """
    unknown = values_seen - known_values
    if unknown:
        print(f"⚠️  Unrecognized {label} value(s), not yet mapped: {unknown}")
    return unknown


def upsert_pet_local(cur, pet: dict) -> None:
    """
    Writes one normalized pet dict directly into the LOCAL `pets` table.
    Script A doesn't need matching_logic.py's AI-extraction/fuzzy-match
    machinery -- that exists for messy social captions with no reliable
    ID. Official shelter feeds already hand us a clean pet_id, so this
    is a plain upsert, same shape as publish.py's upsert_pet() but
    targeting LOCAL instead of REMOTE.

    Expects `pet` to have at least: pet_id, shelter_name. All other
    keys are optional and should match pets table column names.
    """
    columns = [
        "pet_id", "name", "species", "breed", "age", "sex",
        "shelter_name", "shelter_location", "intake_date", "intake_reason",
        "deadline_timestamp", "status", "description", "image_url",
    ]
    values = {c: pet.get(c) for c in columns}

    cur.execute(
        f"""
        INSERT INTO pets ({', '.join(columns)})
        VALUES ({', '.join(f'%({c})s' for c in columns)})
        ON CONFLICT (pet_id) DO UPDATE SET
            {', '.join(f"{c} = EXCLUDED.{c}" for c in columns if c != 'pet_id')},
            updated_at = now()
        """,
        values,
    )


def touch_last_seen(cur, pet_ids: list) -> None:
    """
    Marks these pet_ids as seen in this scrape cycle. Combined with
    mark_missing_as_resolved(), this is how Script A detects an animal
    dropping off a shelter's feed (adopted, transferred, or worse)
    without the shelter explicitly telling us the outcome.
    """
    if not pet_ids:
        return
    cur.execute(
        "UPDATE pets SET last_seen_in_scrape_at = now() WHERE pet_id = ANY(%s)",
        (pet_ids,),
    )


def mark_missing_as_resolved(cur, shelter_name: str, seen_pet_ids: list, grace_period_hours: int = 12) -> int:
    """
    Any AT_RISK pet from this shelter that wasn't in this scrape's
    results, and hasn't been seen in over `grace_period_hours`, gets
    archived. This does NOT mark them EUTHANIZED -- that's a claim that
    needs actual confirmation (see README section on this), not an
    inference from "they disappeared." ARCHIVED means "no longer
    confirmed at-risk per this shelter's feed, outcome unknown" -- a
    human can promote it to a real outcome once known.
    """
    cur.execute(
        f"""
        UPDATE pets
        SET status = 'ARCHIVED'
        WHERE shelter_name = %s
          AND status = 'AT_RISK'
          AND NOT (pet_id = ANY(%s))
          AND (last_seen_in_scrape_at IS NULL OR last_seen_in_scrape_at < now() - interval '{int(grace_period_hours)} hours')
        """,
        (shelter_name, seen_pet_ids),
    )
    return cur.rowcount
