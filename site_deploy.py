"""
site_deploy.py

Rebuilds the public site (launch defaults: no dog, no Remembered) and deploys it to
Cloudflare (wrangler.jsonc, Worker "fadingheartbeats"). Called by run_scheduled.py
with --site (after a scrape) or --site-only (midnight re-sort, no scrape).

Each publish:
  1. Builds into SITE_PUBLIC_DIR.
  2. Refuses to deploy a build that looks wrong (0 animals, under half of the last
     deployed count, a page without the Google tag, any dog file). The live site then
     keeps its previous version.
  3. Deploys with the repo's pinned wrangler, using CLOUDFLARE_API_TOKEN from the shared
     ~/.config/cloudflare/deploy.env (one token for every site; aidegenerates links it too).
  4. Reads the live home page back until it shows this build's stamp.
  5. Appends one line to SITE_LOG_PATH (separate from the scrape run log).
"""

import importlib.util
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import db

LIVE_URL = "https://fadingheartbeats.com/"
LOCAL_TZ = ZoneInfo("America/Chicago")
GA_MARK = "googletagmanager.com/gtag/js?id=G-F98F38JQ09"
MIN_SHARE_OF_LAST = 0.5
LIVE_TRIES = 6
LIVE_WAIT = 10  # seconds between live checks
TOKEN_WARN_DAYS = 14


def load_cloudflare_env():
    """Read CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID from the shared file. A real env var still wins."""
    from dotenv import load_dotenv
    load_dotenv(os.environ.get("CLOUDFLARE_ENV_FILE") or Path.home() / ".config/cloudflare/deploy.env", override=False)


def public_dir() -> Path:
    return Path(os.environ.get("SITE_PUBLIC_DIR") or "/Volumes/Extreme/heartbeats-data/site-public")


def site_log_path() -> Path:
    p = Path(os.environ.get("SITE_LOG_PATH") or "")
    if not str(p) or str(p) == ".":
        import run_scheduled
        p = run_scheduled.run_log_path().with_name("site_deploys.jsonl")
    return p if p.is_absolute() else db.REPO_DIR / p


def build_public(out: Path) -> dict:
    spec = importlib.util.spec_from_file_location("build_site", db.REPO_DIR / "design" / "build_site.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build(out, show_remembered=False, show_dog=False, show_picker=None)


def wrangler_deploy(out: Path) -> tuple:
    """(ok, last lines of output). Runs the pinned wrangler with node found even under cron's short PATH."""
    node = shutil.which("node") or str(Path.home() / ".local/bin/node")
    cli = db.REPO_DIR / "node_modules" / "wrangler" / "bin" / "wrangler.js"
    env = dict(os.environ, WRANGLER_SEND_METRICS="false", CI="1")
    try:
        p = subprocess.run([node, str(cli), "deploy"], cwd=db.REPO_DIR, env=env,
                           capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"{type(e).__name__}: {e}"
    tail = "\n".join((p.stdout + p.stderr).strip().splitlines()[-8:])
    return p.returncode == 0, tail


def fetch_live(url: str) -> str:
    import requests
    return requests.get(url, timeout=20, headers={"Cache-Control": "no-cache"}).text


def _read_log() -> list:
    path = site_log_path()
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def last_deployed_count():
    for r in reversed(_read_log()):
        if r.get("deployed"):
            return r.get("at_risk")
    return None


def check_build(out: Path, res: dict) -> list:
    problems = []
    n = res.get("at_risk") or 0
    if n == 0:
        problems.append("0 animals in the build")
    last = last_deployed_count()
    if n and last and n < last * MIN_SHARE_OF_LAST:
        problems.append(f"only {n} animals vs {last} last deploy (under half)")
    pages = list(out.rglob("*.html"))
    if not pages:
        problems.append("no pages built")
    no_ga = [str(p.relative_to(out)) for p in pages if GA_MARK not in p.read_text()]
    if no_ga:
        problems.append(f"{len(no_ga)} page(s) missing the analytics tag, e.g. {no_ga[0]}")
    dogs = [str(p.relative_to(out)) for p in out.rglob("*") if "dog" in p.name.lower()]
    if dogs:
        problems.append(f"dog files in the build, e.g. {dogs[0]}")
    return problems


def publish(build_fn=build_public, deploy_fn=wrangler_deploy, fetch_fn=fetch_live, sleep=time.sleep) -> dict:
    load_cloudflare_env()
    out = public_dir()
    rec = {"at": db.utcnow(), "ok": False, "deployed": False}
    try:
        res = build_fn(out)
        rec["at_risk"], rec["built"] = res.get("at_risk"), res.get("built")
        problems = check_build(out, res)
        if problems:
            rec["skipped"], rec["error"] = True, "; ".join(problems)
        else:
            ok, tail = deploy_fn(out)
            if not ok:
                rec["error"] = "deploy failed: " + tail[-600:]
            else:
                rec["deployed"] = True
                for i in range(LIVE_TRIES):
                    try:
                        if f'content="{rec["built"]}"' in fetch_fn(f"{LIVE_URL}?v={rec['built']}"):
                            rec["ok"] = True
                            break
                    except Exception:
                        pass
                    if i < LIVE_TRIES - 1:
                        sleep(LIVE_WAIT)
                if not rec["ok"]:
                    rec["error"] = f"deployed, but the live site doesn't show build {rec['built']} yet"
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    path = site_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def alert(rec: dict) -> str:
    if rec.get("ok"):
        return ""
    if rec.get("deployed"):
        return f"⚠️ Heartbeats site: {rec.get('error')}. Check {LIVE_URL}"
    return ("⚠️ Heartbeats site NOT updated: " + str(rec.get("error"))[:700] +
            "\nfadingheartbeats.com still shows the previous version. Next run will retry.")


def summary_line(now: datetime = None) -> str:
    now = now or datetime.now(timezone.utc)
    since = db._fmt(now - timedelta(hours=24))
    recent = [r for r in _read_log() if r.get("at", "") >= since]
    good = [r for r in recent if r.get("ok")]
    bad = len(recent) - len(good)
    if not good:
        return f"⚠️ Site not updated in 24h ({bad} failed attempt{'s' if bad != 1 else ''})"
    last = good[-1]
    when = db.parse_ts(last["at"]).astimezone(LOCAL_TZ).strftime("%-I:%M %p")
    line = f"🌐 Site updated {when} · {last.get('at_risk')} animals"
    return line + (f" ({bad} failed)" if bad else "")


def _get_json(url: str, token: str) -> dict:
    import requests
    return requests.get(url, timeout=20, headers={"Authorization": f"Bearer {token}"}).json()


def token_warning(now: datetime = None, get_json=_get_json) -> str:
    """Warn before the deploy token expires or once it stops working. Never prints the token."""
    load_cloudflare_env()
    token, account = os.environ.get("CLOUDFLARE_API_TOKEN"), os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not token or not account:
        return "⚠️ CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID missing from ~/.config/cloudflare/deploy.env: the site can't deploy"
    now = now or datetime.now(timezone.utc)
    try:
        d = get_json(f"https://api.cloudflare.com/client/v4/accounts/{account}/tokens/verify", token)
    except Exception as e:
        return f"⚠️ Couldn't check the Cloudflare token ({type(e).__name__})"
    r = d.get("result") or {}
    if not d.get("success") or r.get("status") != "active":
        return "⚠️ Cloudflare deploy token is not working: make a new one and put it in ~/.config/cloudflare/deploy.env"
    exp = r.get("expires_on")
    if exp:
        days = (datetime.fromisoformat(exp.replace("Z", "+00:00")) - now).days
        if days < TOKEN_WARN_DAYS:
            return f"⚠️ Cloudflare deploy token expires in {days} days ({exp[:10]}): make a new one and put it in ~/.config/cloudflare/deploy.env"
    return ""
