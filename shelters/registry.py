"""
shelters/registry.py

Per-shelter facts the public site needs, keyed by the exact
`pets.shelter_name` the scraper stores. Add one entry per new shelter.

Why it lives here and not in the site code: the "Foster or adopt"
button must send people to the shelter the animal is actually in, and
every shelter platform builds that link differently. Keep the link
template next to the scraper that knows the platform, verify it live
before adding it, and the site just looks it up.
"""

from typing import Optional
from urllib.parse import quote

SHELTERS = {
    "Dallas Animal Services": {
        "short_name": "Dallas Animal Services",
        # Location: used for the per-shelter page (/tx/dallas/), the
        # "Choose your shelter" menu, and later the map / "Near me".
        "slug": "dallas",            # unique within the state, URL-safe
        "city": "Dallas",
        "state": "TX",
        "state_name": "Texas",
        "address": "1818 N Westmoreland Rd, Dallas, TX 75212",
        # OpenStreetMap amenity=animal_shelter "Dallas Animal Services", checked 2026-10-20.
        "lat": 32.768752,
        "lon": -96.872848,
        "timezone": "America/Chicago",
        # Verified 2026-10-19: returns 200 and shows the animal's name.
        # (https://24petconnect.com/DLLS/Details/<id> is a 404.)
        "adopt_url": "https://24petconnect.com/DallasAdoptions/Details/DLLS/{pet_id}",
        "contact_email": "dasadopt@dallas.gov",
        "website": "https://bedallas90.org/",
    },
}


def shelter_info(shelter_name: str) -> Optional[dict]:
    return SHELTERS.get(shelter_name)


def shelter_path(shelter_name: str) -> Optional[str]:
    """Site path for a shelter's own page, e.g. "tx/dallas", or None if unregistered."""
    info = SHELTERS.get(shelter_name)
    return f"{info['state'].lower()}/{info['slug']}" if info else None


def shelters_by_state() -> list:
    """[(state_name, [(shelter_name, info), ...]), ...] sorted for menus."""
    out: dict = {}
    for name, info in SHELTERS.items():
        out.setdefault(info["state_name"], []).append((name, info))
    return [(st, sorted(v, key=lambda x: (x[1]["city"], x[1]["short_name"]))) for st, v in sorted(out.items())]


def adopt_url(shelter_name: str, pet_id: str) -> Optional[str]:
    """Link to this animal's own page at its shelter, or None if the
    shelter isn't registered (the site must then hide the button rather
    than link somewhere wrong)."""
    info = SHELTERS.get(shelter_name)
    if not info or not pet_id:
        return None
    return info["adopt_url"].format(pet_id=quote(str(pet_id), safe=""))
