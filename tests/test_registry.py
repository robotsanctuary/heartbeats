from shelters import registry
from shelters.texas import dallas


def test_every_scraper_shelter_is_registered():
    assert registry.shelter_info(dallas.SHELTER_NAME) is not None


def test_dallas_adopt_url_is_the_verified_pattern():
    assert (registry.adopt_url("Dallas Animal Services", "A1301309")
            == "https://24petconnect.com/DallasAdoptions/Details/DLLS/A1301309")


def test_unknown_shelter_gets_no_link():
    # Better no button than a button to the wrong shelter.
    assert registry.adopt_url("Some Other Shelter", "A1") is None


def test_missing_pet_id_gets_no_link():
    assert registry.adopt_url("Dallas Animal Services", "") is None


def test_pet_id_is_url_escaped():
    url = registry.adopt_url("Dallas Animal Services", "A1/../x?y")
    assert "/../" not in url and "?" not in url


def test_every_shelter_has_a_location():
    import re
    seen = set()
    for name, info in registry.SHELTERS.items():
        for k in ("slug", "city", "state", "state_name", "lat", "lon"):
            assert info.get(k) not in (None, ""), (name, k)
        assert re.fullmatch(r"[a-z0-9-]+", info["slug"]), name
        assert re.fullmatch(r"[A-Z]{2}", info["state"]), name
        assert 18 <= info["lat"] <= 72 and -180 <= info["lon"] <= -60, name  # inside the US
        path = registry.shelter_path(name)
        assert path not in seen, f"duplicate page path {path}"
        seen.add(path)


def test_shelter_path():
    assert registry.shelter_path("Dallas Animal Services") == "tx/dallas"
    assert registry.shelter_path("Nope") is None
