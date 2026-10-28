"""Public site auto-deploy: safety checks before deploy, live check after, alerts, summary line. Never hits Cloudflare."""

import json
from datetime import datetime, timedelta, timezone

import pytest

import run_scheduled as rs
import site_deploy as sd

GA = '<script async src="https://www.googletagmanager.com/gtag/js?id=G-F98F38JQ09"></script>'
BUILT = "2026-10-28T02:02:30Z"


@pytest.fixture(autouse=True)
def logs(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_LOG_PATH", str(tmp_path / "runs.jsonl"))
    monkeypatch.setenv("SITE_PUBLIC_DIR", str(tmp_path / "public"))


def fake_build(n=99, ga=True, dog=False):
    def build(out):
        out.mkdir(parents=True, exist_ok=True)
        page = f'<html><head>{GA if ga else ""}<meta name="hb-built" content="{BUILT}"></head><body></body></html>'
        (out / "index.html").write_text(page)
        (out / "help.html").write_text(page)
        if dog:
            (out / "dog.png").write_bytes(b"x")
        return {"at_risk": n, "built": BUILT}
    return build


class Deploy:
    def __init__(self, ok=True, out="Deployed fadingheartbeats triggers"):
        self.calls, self.ok, self.out = 0, ok, out

    def __call__(self, out_dir):
        self.calls += 1
        return self.ok, self.out


def live(stamp=BUILT):
    return lambda url: f'<meta name="hb-built" content="{stamp}">'


def publish(build=None, deploy=None, fetch=None):
    return sd.publish(build_fn=build or fake_build(), deploy_fn=deploy or Deploy(),
                      fetch_fn=fetch or live(), sleep=lambda s: None)


def logged():
    return [json.loads(l) for l in sd.site_log_path().read_text().splitlines()]


def test_happy_path_deploys_checks_live_and_is_quiet():
    d = Deploy()
    rec = publish(deploy=d)
    assert rec["ok"] and rec["deployed"] and d.calls == 1 and rec["at_risk"] == 99
    assert sd.alert(rec) == ""
    assert logged()[-1]["ok"] is True
    assert "Site updated" in sd.summary_line() and "99 animals" in sd.summary_line()


def test_site_log_is_separate_from_scrape_runs():
    publish()
    assert not rs.run_log_path().exists()          # scrape "Runs (24h)" counts stay honest
    assert "0 ok" in rs.build_summary()


@pytest.mark.parametrize("build, why", [
    (fake_build(n=0), "0 animals"),
    (fake_build(ga=False), "analytics"),
    (fake_build(dog=True), "dog"),
])
def test_bad_build_is_never_deployed(build, why):
    d = Deploy()
    rec = publish(build=build, deploy=d)
    assert d.calls == 0 and not rec["ok"] and not rec["deployed"]
    a = sd.alert(rec)
    assert "NOT updated" in a and why in a and "still shows the previous version" in a


def test_big_drop_against_last_deploy_is_not_deployed():
    publish(build=fake_build(n=100))
    d = Deploy()
    rec = publish(build=fake_build(n=49), deploy=d)
    assert d.calls == 0 and "100" in sd.alert(rec) and "49" in sd.alert(rec)
    rec = publish(build=fake_build(n=50), deploy=d)  # half is still allowed
    assert d.calls == 1 and rec["ok"]


def test_failed_deploys_dont_lower_the_bar():
    publish(build=fake_build(n=100))
    publish(build=fake_build(n=10))                 # refused
    assert sd.last_deployed_count() == 100


def test_deploy_error_alerts_with_output():
    rec = publish(deploy=Deploy(ok=False, out="Authentication error [code: 10000]"))
    assert not rec["ok"] and "Authentication error" in sd.alert(rec)


def test_build_crash_alerts():
    def boom(out):
        raise RuntimeError("db locked")
    d = Deploy()
    rec = publish(build=boom, deploy=d)
    assert d.calls == 0 and "db locked" in sd.alert(rec)


def test_live_site_not_showing_new_build_alerts():
    rec = publish(fetch=live("2026-10-27T00:00:00Z"))
    assert rec["deployed"] and not rec["ok"]
    assert "live site" in sd.alert(rec)


def test_live_check_retries_then_passes():
    seen = iter(["old", "old", f'content="{BUILT}"'])
    rec = publish(fetch=lambda url: next(seen))
    assert rec["ok"]


def test_live_check_network_error_is_retried():
    calls = []
    def flaky(url):
        calls.append(url)
        if len(calls) < 2:
            raise OSError("timeout")
        return f'content="{BUILT}"'
    assert publish(fetch=flaky)["ok"]
    assert all(BUILT in u for u in calls)                 # cache-busting query on each try


def test_summary_line_warns_when_nothing_deployed_today(monkeypatch):
    assert "not updated in 24h" in sd.summary_line()
    publish()
    later = datetime.now(timezone.utc) + timedelta(hours=30)
    assert "not updated in 24h" in sd.summary_line(now=later)


@pytest.mark.parametrize("resp, warn", [
    ({"success": True, "result": {"status": "active", "expires_on": "2026-11-01T05:59:59Z"}}, "expires in 4 days"),
    ({"success": True, "result": {"status": "active", "expires_on": "2027-01-26T05:59:59Z"}}, ""),
    ({"success": True, "result": {"status": "active"}}, ""),
    ({"success": False, "errors": [{"message": "Invalid API Token"}]}, "token is not working"),
])
def test_token_expiry_warning(resp, warn, monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "t")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a")
    now = datetime(2026, 10, 28, tzinfo=timezone.utc)
    got = sd.token_warning(now=now, get_json=lambda url, token: resp)
    assert (warn in got) if warn else got == ""


def test_token_warning_when_missing(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    assert "CLOUDFLARE_API_TOKEN" in sd.token_warning(get_json=lambda u, t: {})


def test_site_only_run_does_not_scrape(monkeypatch):
    monkeypatch.setattr(rs, "run_all", lambda: pytest.fail("scraped"))
    monkeypatch.setattr(sd, "publish", lambda: {"ok": True, "deployed": True, "at_risk": 1, "built": BUILT})
    assert rs.main(["--site-only"]) == ""


def test_site_run_scrapes_then_deploys_and_reports_failure(monkeypatch):
    order = []
    monkeypatch.setattr(rs, "run_all", lambda: order.append("scrape") or [])
    monkeypatch.setattr(sd, "publish", lambda: order.append("site") or
                        {"ok": False, "deployed": False, "error": "0 animals in the build", "skipped": True})
    out = rs.main(["--site"])
    assert order == ["scrape", "site"] and "NOT updated" in out


def test_plain_run_does_not_deploy(monkeypatch):
    monkeypatch.setattr(rs, "run_all", lambda: [])
    monkeypatch.setattr(sd, "publish", lambda: pytest.fail("deployed"))
    assert rs.main([]) == ""
