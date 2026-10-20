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
