"""
shelters/texas/dallas.py

Dallas Animal Services. Two validated data sources, both from the same
24petconnect.com feed platform, no headless browser or PDF parsing
needed:

  - PRE_LAB_FEED_URL: animals with a scheduled euthanasia deadline
  - NEONATE_FEED_URL: underage animals needing an immediate foster
    (no fixed deadline -- age-based urgency instead)

Confirmed via an unfiltered feed diff (2026-07-25) that these two feeds
together capture every currently UrgentPet=Yes / KennelStatus=PRE-LAB
animal in Dallas's public data -- there is no third missing category
today. "Rescue Only" / "Emergency Rescue" (mentioned on
bedallas90.org/mvp/) appear to be editorial labels applied to specific
PRE-LAB animals rather than a separate feed, and simply had zero
animals in them at last check. See check_unknown_categories() below --
if a Pathway value we've never seen shows up, this script will flag it
rather than silently drop it.

Usage:
    python -m shelters.texas.dallas              # dry run, prints only
    python -m shelters.texas.dallas --write       # writes to LOCAL_DATABASE_URL
"""

import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from shelters.common import (
    check_unknown_categories,
    fetch_xml,
    get_local_conn,
    mark_missing_as_resolved,
    strip_html,
    touch_last_seen,
    upsert_pet_local,
)
from image_archive import archive_image

SHELTER_NAME = "Dallas Animal Services"

# Dallas reports dates in its own local time. Dates are stored as
# midnight *Dallas time* (not UTC), otherwise "8/2" lands in Postgres as
# 8/1 7pm Central and shows up a day early on the site.
SHELTER_TZ = ZoneInfo("America/Chicago")

PRE_LAB_FEED_URL = "https://24petconnect.com/RSS/RSSFeed?id=td48ev36&sl=DLLS&KennelStatus=PRE-LAB"
NEONATE_FEED_URL = "https://24petconnect.com/RSS/RSSFeed?id=td48ev36&sl=DLLS&Neonate=Yes"

# Confirmed against live pulls. Update this set the moment
# check_unknown_categories() flags something new -- that's the signal
# a genuinely new outcome type exists, not a reason to ignore the warning.
KNOWN_OUTCOME_TYPES = {"RTO", "TRANSFER", "ADOPTION", "FOSTER"}
OUTCOME_TYPE_TO_STATUS = {
    "RTO": "SAFE",
    "TRANSFER": "TRANSFERRED",
    "ADOPTION": "ADOPTED",
    "FOSTER": "SAFE",  # out of the shelter in a foster home (seen live 2026-10-19)
}
# An outcome type we haven't mapped yet is NOT assumed safe -- it gets
# PENDING_VERIFICATION so a human checks it instead of it quietly
# disappearing from the at-risk list as "SAFE".
UNKNOWN_OUTCOME_STATUS = "PENDING_VERIFICATION"

# Every Pathway value seen across PRE-LAB + Neonate pulls so far.
# "RESCUE ONLY" is NOT in here on purpose -- if they
# ever appear, check_unknown_categories() should flag them loudly.
# "EM RESCUE" (emergency rescue) first seen in the live PRE-LAB feed 2026-10-19.
KNOWN_PATHWAYS = {"ADOP RESCU", "RESC FOSTR", "QUARANTINE", "EM RESCUE", None}


def _text(item, tag: str):
    el = item.find(tag)
    if el is None or el.text is None or not el.text.strip():
        return None
    return el.text.strip()


def _parse_mmddyyyy(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y").replace(tzinfo=SHELTER_TZ).isoformat()
    except ValueError:
        return None


def normalize_item(item, source: str) -> dict:
    breed_parts = [p for p in (_text(item, "PrimaryBreed"), _text(item, "SecondaryBreed")) if p]
    outcome_type = _text(item, "OutcomeType")
    animal_type = _text(item, "AnimalType")

    return {
        "pet_id": _text(item, "Animal_ID"),
        "name": _text(item, "AnimalName"),
        "species": animal_type.upper() if animal_type in ("Dog", "Cat") else "OTHER",
        "breed": " / ".join(breed_parts) if breed_parts else None,
        "age": _text(item, "AnimalAge"),
        "sex": _text(item, "AnimalSex"),
        "shelter_name": SHELTER_NAME,
        "shelter_location": _text(item, "Location"),
        "intake_date": _parse_mmddyyyy(_text(item, "IntakeDate")),
        "intake_reason": _text(item, "KennelSubstatus"),
        "deadline_timestamp": _parse_mmddyyyy(_text(item, "EmergencyPlacementDate")),
        "description": strip_html(_text(item, "WebMemo")),
        "outcome_type": outcome_type,
        "status": (
            "AT_RISK" if outcome_type is None
            else OUTCOME_TYPE_TO_STATUS.get(outcome_type, UNKNOWN_OUTCOME_STATUS)
        ),
        "image_url": _text(item, "imageURL"),
        "pathway": _text(item, "Pathway"),
        "source": source,
    }


def fetch_and_normalize() -> list:
    pre_lab_root = fetch_xml(PRE_LAB_FEED_URL)
    neonate_root = fetch_xml(NEONATE_FEED_URL)

    pre_lab_items = [normalize_item(i, "pre_lab") for i in pre_lab_root.findall(".//item")]
    neonate_items = [normalize_item(i, "neonate") for i in neonate_root.findall(".//item")]

    # Dedup by pet_id, preferring pre_lab (richer data: deadline + description).
    by_pet_id = {}
    for n in neonate_items + pre_lab_items:
        by_pet_id[n["pet_id"]] = n
    return list(by_pet_id.values())


def run(write: bool = False):
    animals = fetch_and_normalize()
    print(f"[Dallas] Fetched {len(animals)} unique at-risk/underage animals.")

    outcome_types_seen = {a["outcome_type"] for a in animals if a["outcome_type"]}
    check_unknown_categories(outcome_types_seen, KNOWN_OUTCOME_TYPES, "OutcomeType")

    pathways_seen = {a["pathway"] for a in animals}
    check_unknown_categories(pathways_seen, KNOWN_PATHWAYS, "Pathway")

    if not write:
        print("[Dallas] Dry run only -- pass --write to save to LOCAL_DATABASE_URL.")
        for a in animals[:5]:
            print(f"  {a['pet_id']:<12} {a['status']:<12} {a['name']}")
        if len(animals) > 5:
            print(f"  ...and {len(animals) - 5} more")
        return {"fetched": len(animals), "written": False}

    with get_local_conn() as conn:
        with conn.cursor() as cur:
            for animal in animals:
                upsert_pet_local(cur, animal)

                # Download the photo now, while it's still available --
                # not later, once an outcome is known. See
                # image_archive.py for the full retention rationale.
                if animal.get("image_url"):
                    try:
                        local_path = archive_image(animal["pet_id"], animal["image_url"])
                        if local_path:
                            cur.execute(
                                "UPDATE pets SET local_image_path = %s WHERE pet_id = %s",
                                (local_path, animal["pet_id"]),
                            )
                    except Exception as e:
                        # A failed image download shouldn't block ingesting
                        # the rest of the animal's data -- log and move on.
                        print(f"[Dallas] ⚠️  Image archive failed for {animal['pet_id']}: {e}")

            pet_ids = [a["pet_id"] for a in animals]
            touch_last_seen(cur, pet_ids)
            archived_count = mark_missing_as_resolved(cur, SHELTER_NAME, pet_ids)
        conn.commit()

    print(f"[Dallas] Wrote {len(animals)} animals to LOCAL_DATABASE_URL. "
          f"Archived {archived_count} animal(s) no longer appearing in either feed.")
    return {"fetched": len(animals), "written": True, "archived": archived_count}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dallas Animal Services scraper.")
    parser.add_argument("--write", action="store_true", help="Write results to LOCAL_DATABASE_URL instead of a dry run.")
    args = parser.parse_args()
    run(write=args.write)
