"""
Shared helpers used by every pipeline script.

Keeping these in one place means:
  - every script writes the cleaning log and source register the same way,
  - every API call gets the same retry / sleep behaviour,
  - YouTube quota is counted in one file, so we never blow the 10,000 units/day limit.
"""

import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

# --- Folder paths ---------------------------------------------------------
# Every script imports these instead of hard-coding paths, so the repo
# works no matter which folder you run `make` from.
ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_INTERIM = ROOT / "data" / "interim"
DATA_CLEAN = ROOT / "data" / "clean"
DATA_MANUAL = ROOT / "data" / "manual"
OUT_TABLES = ROOT / "outputs" / "tables"
OUT_CHARTS = ROOT / "outputs" / "charts"
CLEANING_LOG = ROOT / "outputs" / "cleaning_log.csv"
SOURCE_LOG = DATA_RAW / "source_access_log.csv"
QUOTA_FILE = DATA_RAW / "youtube_quota.json"

# --- Secrets --------------------------------------------------------------
# Keys live in .env (gitignored). load_dotenv copies them into os.environ.
load_dotenv(ROOT / ".env")


def get_env(name):
    """Return an environment variable, or stop with a clear message if it is missing."""
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing {name} in .env — see MANUAL_STEPS.md")
    return value


# --- Cleaning log ---------------------------------------------------------
# One row per cleaning decision. Each script appends its own rows with the
# real counts it measured, so the log is never typed by hand.
CLEANING_LOG_COLUMNS = ["id", "stage", "problem_found", "rows_affected", "action_taken", "why"]


def log_cleaning(stage, problem_found, rows_affected, action_taken, why):
    """Append one decision to outputs/cleaning_log.csv (creates the file if needed)."""
    CLEANING_LOG.parent.mkdir(parents=True, exist_ok=True)
    is_new = not CLEANING_LOG.exists()

    # The next id is simply "how many rows are already there + 1".
    next_id = 1
    if not is_new:
        with open(CLEANING_LOG, newline="", encoding="utf-8") as f:
            next_id = sum(1 for _ in csv.reader(f))  # header counts as 1, so this is rows+1

    with open(CLEANING_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(CLEANING_LOG_COLUMNS)
        writer.writerow([next_id, stage, problem_found, int(rows_affected), action_taken, why])


def reset_cleaning_log_for_stage(stage):
    """Remove earlier rows from one stage, so re-running a script does not duplicate its entries."""
    if not CLEANING_LOG.exists():
        return
    with open(CLEANING_LOG, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["stage"] != stage]

    # Re-number ids so they stay 1, 2, 3, ...
    with open(CLEANING_LOG, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CLEANING_LOG_COLUMNS)
        writer.writeheader()
        for i, row in enumerate(rows, start=1):
            row["id"] = i
            writer.writerow(row)


# --- Source access log ----------------------------------------------------
# Every successful pull writes one line here. The source register
# (outputs/tables/source_register.csv) is built from this file, so its
# access dates are real, not remembered.
def log_source_access(source, url, method, note):
    SOURCE_LOG.parent.mkdir(parents=True, exist_ok=True)
    is_new = not SOURCE_LOG.exists()
    with open(SOURCE_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["source", "url", "method", "accessed_utc", "note"])
        writer.writerow([source, url, method, now_utc_iso(), note])


def now_utc_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Polite HTTP GET with retries ----------------------------------------
# APIs sometimes fail for a moment (rate limit 429, server error 5xx).
# We wait and try again a few times, doubling the wait each time,
# instead of hammering the server or crashing on the first hiccup.
def http_get_json(url, params=None, headers=None, max_tries=4, pause_s=1.0):
    # YouTube must go through youtube_get(), which enforces the daily quota limit.
    if "googleapis.com/youtube" in url:
        raise RuntimeError("Use youtube_get() for YouTube calls — it enforces the 10,000-unit limit")

    wait = pause_s
    for attempt in range(1, max_tries + 1):
        response = requests.get(url, params=params, headers=headers, timeout=30)

        if response.status_code == 200:
            time.sleep(pause_s)  # small pause between calls = respecting rate limits
            return response.json()

        retryable = response.status_code == 429 or response.status_code >= 500
        if not retryable or attempt == max_tries:
            # Show the API's own error message — it usually says exactly what is wrong.
            raise RuntimeError(f"GET {url} failed {response.status_code}: {response.text[:300]}")

        print(f"  HTTP {response.status_code}, retry {attempt}/{max_tries} in {wait:.0f}s")
        time.sleep(wait)
        wait = wait * 2


# --- YouTube quota guard --------------------------------------------------
# YouTube gives 10,000 units per day per Google Cloud project, and the day
# resets at midnight PACIFIC time (not IST, not UTC).
#
# Hard rule: no code in this repo may spend more than 10,000 units in one
# Pacific day. We enforce it like this:
#   1. youtube_get() is the ONLY way to call YouTube. http_get_json() refuses
#      YouTube URLs, so nobody can bypass the guard by accident.
#   2. Each call's cost is looked up BEFORE it is sent. Unknown endpoints are
#      refused, so a cost can never be guessed wrong.
#   3. The units are reserved (written to the quota file) BEFORE the request
#      goes out. If the reservation would pass the limit, the call is never
#      made. Failed requests stay counted, because Google charges them too.
#   4. Every retry is a new request, so it reserves its own units.
#   5. A file lock stops two scripts running at once from both squeezing
#      under the limit at the same moment.
#   6. If Google itself says the quota is used up, we mark today as full
#      so no later script in the same day even tries.
YT_HARD_LIMIT = 10_000

# Cost in units per call, from https://developers.google.com/youtube/v3/determine_quota_cost
YT_COSTS = {
    "videos": 1,
    "commentThreads": 1,
    "channels": 1,
    "playlistItems": 1,
    "search": 100,
}

YT_BASE = "https://www.googleapis.com/youtube/v3/"
QUOTA_LOCK = DATA_RAW / "youtube_quota.lock"

try:
    import fcntl  # file locking on macOS / Linux
except ImportError:  # Windows has no fcntl; there we rely on running one script at a time
    fcntl = None


class YouTubeQuotaExceeded(RuntimeError):
    """Raised instead of making a call that would go past the daily limit."""


def youtube_daily_budget():
    """The limit we enforce. .env may LOWER it (YT_DAILY_BUDGET=5000) but can never raise it above 10,000."""
    requested = os.getenv("YT_DAILY_BUDGET", "").strip()
    if requested.isdigit():
        return min(int(requested), YT_HARD_LIMIT)
    return YT_HARD_LIMIT


def _pacific_today():
    # The quota day follows Pacific time, so "today" must too.
    return datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")


def _read_usage():
    if QUOTA_FILE.exists():
        return json.loads(QUOTA_FILE.read_text())
    return {}


def _reserve_units(units):
    """Add units to today's total, or raise if that would pass the budget. Runs under a file lock."""
    QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
    budget = youtube_daily_budget()

    with open(QUOTA_LOCK, "w") as lock:
        if fcntl:
            fcntl.flock(lock, fcntl.LOCK_EX)  # wait here if another script holds the lock

        usage = _read_usage()
        today = _pacific_today()
        used = usage.get(today, 0)

        if used + units > budget:
            raise YouTubeQuotaExceeded(
                f"Refusing YouTube call: {used} + {units} units would pass today's limit of {budget} "
                f"(resets midnight Pacific time)."
            )

        usage[today] = used + units
        QUOTA_FILE.write_text(json.dumps(usage, indent=2))
        return usage[today]


def _mark_quota_full():
    """Google said we are out of quota: record today as full so nothing else tries."""
    with open(QUOTA_LOCK, "w") as lock:
        if fcntl:
            fcntl.flock(lock, fcntl.LOCK_EX)
        usage = _read_usage()
        usage[_pacific_today()] = youtube_daily_budget()
        QUOTA_FILE.write_text(json.dumps(usage, indent=2))


def youtube_get(endpoint, params, max_tries=3, pause_s=1.0):
    """Call one YouTube Data API endpoint (e.g. "videos") with the quota guard. Returns parsed JSON."""
    if endpoint not in YT_COSTS:
        raise ValueError(f"Unknown YouTube endpoint '{endpoint}' — add its cost to YT_COSTS first")
    cost = YT_COSTS[endpoint]
    url = YT_BASE + endpoint

    wait = pause_s
    for attempt in range(1, max_tries + 1):
        used = _reserve_units(cost)  # raises BEFORE sending if we would go over
        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 200:
            time.sleep(pause_s)
            return response.json()

        # 403 with reason quotaExceeded = Google's own counter is full (it may include
        # usage from other apps in the same Cloud project that our file can't see).
        if response.status_code == 403 and "quotaExceeded" in response.text:
            _mark_quota_full()
            raise YouTubeQuotaExceeded("Google reports the YouTube quota is used up for today.")

        retryable = response.status_code == 429 or response.status_code >= 500
        if not retryable or attempt == max_tries:
            raise RuntimeError(f"YouTube {endpoint} failed {response.status_code}: {response.text[:300]}")

        print(f"  HTTP {response.status_code}, retry {attempt}/{max_tries} in {wait:.0f}s (quota used today: {used})")
        time.sleep(wait)
        wait = wait * 2


def youtube_quota_today():
    """Units spent so far in the current Pacific day."""
    return _read_usage().get(_pacific_today(), 0)


def print_youtube_quota():
    used = youtube_quota_today()
    budget = youtube_daily_budget()
    print(f"YouTube quota today: {used:,} / {budget:,} units ({budget - used:,} left)")
