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


# --- YouTube quota tracker ------------------------------------------------
# YouTube gives 10,000 units per day (resets midnight Pacific time).
# videos.list / commentThreads.list = 1 unit, search.list = 100 units.
# We keep a running total per day in data/raw/youtube_quota.json.
YT_DAILY_LIMIT = 10_000


def add_youtube_quota(units):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = {}
    if QUOTA_FILE.exists():
        usage = json.loads(QUOTA_FILE.read_text())
    usage[today] = usage.get(today, 0) + units

    QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUOTA_FILE.write_text(json.dumps(usage, indent=2))

    if usage[today] > YT_DAILY_LIMIT * 0.9:
        print(f"  WARNING: YouTube quota at {usage[today]}/{YT_DAILY_LIMIT} today")
    return usage[today]


def youtube_quota_today():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not QUOTA_FILE.exists():
        return 0
    return json.loads(QUOTA_FILE.read_text()).get(today, 0)
