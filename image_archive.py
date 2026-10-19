"""
image_archive.py

Downloads a local copy of each at-risk animal's shelter photo as soon
as they're ingested -- not lazily, not only once euthanasia looks
likely -- because the shelter's own image URL can disappear the moment
the animal's record drops off their feed. By the time an outcome is
confirmed, it may already be too late to grab the photo from the
source. Better to have a local copy for every at-risk animal and only
decide later what to keep.

Retention rule, applied by cleanup_resolved_images():
  - status == EUTHANIZED  -> keep the local file FOREVER (the memorial)
  - status in (SAFE, ADOPTED, TRANSFERRED, ARCHIVED) -> delete the local
    file; the animal is fine, there's no reason to keep it
  - status == AT_RISK / PENDING_VERIFICATION -> leave it alone, outcome
    isn't known yet

Storage estimate: even a generous 1MB/photo, a few hundred animals in
flight at once is a few hundred MB; the permanent memorial archive
(euthanized outcomes only) is on the order of a few GB/year even at
national scale. Not a real constraint on any external SSD.

Usage:
    from image_archive import archive_image, cleanup_resolved_images

    # When first ingesting an AT_RISK animal (Script A):
    local_path = archive_image(pet_id="A1293734", image_url="https://...")

    # Periodically (e.g. once a day, after Script A runs):
    with db.session() as conn:
        cleanup_resolved_images(conn)

Environment:
    LOCAL_IMAGE_DIR   directory on the external SSD to store photos in,
                       e.g. /Volumes/YourSSDName/animal-images
"""

import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from db import REPO_DIR  # also loads .env

USER_AGENT = "heartbeats-shelter-aggregator/0.1 (+https://github.com/robotsanctuary/heartbeats)"

# Only real image types are kept; anything else in a URL path (".php",
# ".aspx", nothing at all) falls back to .jpg.
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def image_dir() -> Path:
    """Read at call time (not import) so tests/scripts can override it.
    Relative paths are resolved against the repo folder, not the cwd."""
    p = Path(os.environ.get("LOCAL_IMAGE_DIR") or "./animal-images").expanduser()
    return p if p.is_absolute() else REPO_DIR / p

# Statuses where the animal is confirmed fine -- no reason to keep a
# local photo copy going forward.
RESOLVED_SAFE_STATUSES = ("SAFE", "ADOPTED", "TRANSFERRED", "ARCHIVED")


def _guess_extension(image_url: str) -> str:
    ext = Path(urlparse(image_url).path).suffix.lower()
    return ext if ext in ALLOWED_EXTENSIONS else ".jpg"  # shelter image endpoints often omit a real extension


def _safe_filename(pet_id: str) -> str:
    """pet_id comes from an outside feed -- never let it become a path
    like '../../x'. Keep only letters, digits, '-' and '_'."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", pet_id or "")
    if not safe.strip("_"):
        raise ValueError(f"unusable pet_id for a filename: {pet_id!r}")
    return safe


def archive_image(pet_id: str, image_url: str) -> Optional[str]:
    """
    Downloads the animal's photo to LOCAL_IMAGE_DIR if not already
    present. Returns the local file path (as a string, suitable for
    pets.local_image_path), or None if the download failed -- a failed
    download shouldn't block the rest of Script A's ingest, so this is
    designed to be called in a try/except by the caller if you want to
    log failures rather than crash a run over one bad image.
    """
    if not image_url:
        return None

    folder = image_dir()
    folder.mkdir(parents=True, exist_ok=True)
    local_path = folder / f"{_safe_filename(pet_id)}{_guess_extension(image_url)}"

    if local_path.exists() and local_path.stat().st_size > 0:
        return str(local_path)

    resp = requests.get(image_url, timeout=30, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "")
    if not resp.content or (content_type and not content_type.startswith("image/")):
        raise ValueError(f"not an image (Content-Type {content_type!r}, {len(resp.content)} bytes)")

    # Write to a temp name, then rename: an interrupted download never
    # leaves a truncated file that later looks like a valid photo.
    tmp = local_path.with_suffix(local_path.suffix + ".part")
    tmp.write_bytes(resp.content)
    tmp.replace(local_path)
    return str(local_path)


def cleanup_resolved_images(conn) -> dict:
    """
    Walks every pet with a local_image_path set and applies the
    retention rule: delete the file for anything resolved safely,
    leave EUTHANIZED files alone forever, leave still-open cases alone.

    `conn` is a connection from db.session(); the caller commits.
    """
    rows = conn.execute(
        """
        SELECT pet_id, local_image_path, status, image_permanently_archived
        FROM pets
        WHERE local_image_path IS NOT NULL
        """
    ).fetchall()

    deleted = 0
    archived = 0
    left_open = 0

    for row in rows:
        pet_id = row["pet_id"]
        path = Path(row["local_image_path"])
        status = row["status"]

        if status == "EUTHANIZED":
            if not row["image_permanently_archived"]:
                conn.execute(
                    "UPDATE pets SET image_permanently_archived = 1 WHERE pet_id = ?",
                    (pet_id,),
                )
            archived += 1

        elif status in RESOLVED_SAFE_STATUSES:
            if path.exists():
                path.unlink()
            conn.execute(
                "UPDATE pets SET local_image_path = NULL WHERE pet_id = ?",
                (pet_id,),
            )
            deleted += 1

        else:
            # AT_RISK / PENDING_VERIFICATION -- outcome not known yet,
            # leave the file exactly as it is.
            left_open += 1

    return {"archived_permanently": archived, "deleted": deleted, "left_open": left_open}


if __name__ == "__main__":
    # Quick manual test: python image_archive.py
    test_url = "https://24Petconnect.com/image/A1293734/DLLS/3"
    path = archive_image(pet_id="A1293734", image_url=test_url)
    print(f"Saved to: {path}")
    print(f"File size: {os.path.getsize(path)} bytes" if path else "Download failed")
