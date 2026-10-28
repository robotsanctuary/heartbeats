"""
Shared test setup. Every test gets its own throwaway SQLite file and
image folder, and no test touches the network or a real LLM:
  - feeds are read from tests/fixtures (real Dallas XML captured 2026-10-19)
  - image downloads and LLM calls are replaced with fakes
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(REPO))


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("LOCAL_IMAGE_DIR", str(tmp_path / "images"))
    monkeypatch.delenv("REMOTE_DATABASE_URL", raising=False)
    # Never read (or deploy with) the real Cloudflare token from tests.
    monkeypatch.setenv("CLOUDFLARE_ENV_FILE", str(tmp_path / "no-cloudflare.env"))
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    import db
    db.init_db()
    yield tmp_path


@pytest.fixture
def conn():
    import db
    c = db.connect()
    yield c
    c.close()


class FakeResponse:
    def __init__(self, content=b"\xff\xd8fakejpeg", content_type="image/jpeg", status=200):
        self.content = content
        self.headers = {"Content-Type": content_type}
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def fake_images(monkeypatch):
    """Replace image downloads with an instant fake JPEG; records calls."""
    import image_archive
    calls = []

    def fake_get(url, timeout=30, headers=None):
        calls.append(url)
        return FakeResponse()

    monkeypatch.setattr(image_archive.requests, "get", fake_get)
    return calls


def item_xml(animal_id="A1", name="Rex", outcome="", pathway="ADOP RESCU",
             deadline="08/02/2026", intake="07/20/2026", animal_type="Dog", image=True):
    img = f"<imageURL>https://24petconnect.com/image/{animal_id}/DLLS/1</imageURL>" if image else ""
    return f"""<item>
      <Animal_ID>{animal_id}</Animal_ID><AnimalName>{name}</AnimalName>
      <AnimalType>{animal_type}</AnimalType><PrimaryBreed>Lab</PrimaryBreed>
      <AnimalAge>2 years</AnimalAge><AnimalSex>Male</AnimalSex><Location>Shelter</Location>
      <IntakeDate>{intake}</IntakeDate><KennelSubstatus>SPACE</KennelSubstatus>
      <EmergencyPlacementDate>{deadline}</EmergencyPlacementDate>
      <WebMemo>Sweet &lt;BR&gt;boy</WebMemo><OutcomeType>{outcome}</OutcomeType>
      <Pathway>{pathway}</Pathway>{img}
    </item>"""


def feed_xml(*items):
    return ("<rss><channel>" + "".join(items) + "</channel></rss>").encode()


@pytest.fixture
def fake_feeds(monkeypatch):
    """Point the Dallas scraper at in-memory feeds. Set .prelab / .neonate
    to XML bytes (defaults: the real captured fixtures)."""
    from shelters.texas import dallas
    from shelters import common

    class Feeds:
        prelab = (FIXTURES / "dallas_prelab_live.xml").read_bytes()
        neonate = (FIXTURES / "dallas_neonate_live.xml").read_bytes()

    feeds = Feeds()

    def fake_fetch_xml(url, timeout=30):
        data = feeds.prelab if url == dallas.PRE_LAB_FEED_URL else feeds.neonate
        return common.parse_xml(data)

    monkeypatch.setattr(dallas, "fetch_xml", fake_fetch_xml)
    return feeds
