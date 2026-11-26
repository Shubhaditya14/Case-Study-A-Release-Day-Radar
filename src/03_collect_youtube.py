"""
Step 03 — Collect trailer stats and comments from the YouTube Data API v3 (JSON).

Part A — trailers (all official language versions):
  1. videos.list on the main trailer → its channel and publish time.             (1 unit)
  2. search.list on THAT channel, within 3 days of the main trailer → the other
     language versions (Hindi / Telugu / Tamil ...).                              (100 units)
  3. videos.list on everything found → views, likes, comment counts.              (1 unit)
  We keep videos whose title says "trailer" and drop promos ("out now", "reaction" ...).

Part B — comments on each film's MAIN trailer:
  commentThreads.list returns 100 top-level comments per call (1 unit), NEWEST first.
  To reach the trailer-launch week (needed for velocity) we have to page all the way back,
  so we do not cap at 5,000: a cap would only give us recent comments.
  Every page is saved to disk with its nextPageToken, so if the quota guard stops us,
  re-running the script continues where it left off instead of starting again.

Raw files (data/raw/youtube/) contain author names → gitignored, never committed.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import (DATA_MANUAL, DATA_RAW, YouTubeQuotaExceeded, get_env,  # noqa: E402
                   log_source_access, print_youtube_quota, youtube_get, youtube_quota_today,
                   youtube_daily_budget)

RAW_DIR = DATA_RAW / "youtube"
COMMENTS_DIR = RAW_DIR / "comments"

# Titles with these words are promos, not trailers. All were seen on official channels:
# "Trailer Out now!!", "Trailer Launch Event LIVE", "Ram Charan Speech | Trailer Takeover Event",
# "The Sitaare React!", "candid moments ... #Shorts".
PROMO_WORDS = ["out now", "now streaming", "officially out", "reaction", "react", "concept", "teaser",
               "glimpse", "promo", "review", "song", "lyrical", "making", "launch", "event", "speech",
               "candid", "#shorts", "takes the internet", "crosses", "trending"]

# A dubbed language version is the SAME edit as the main trailer, so its length is almost identical.
# Cut-downs (30 s versions), Shorts and livestreams fail this test even if their title says "trailer".
DURATION_TOLERANCE = 0.10

# Stop pulling comments when this few units are left, so later steps / reruns still have room
UNITS_TO_KEEP_SPARE = 300


# --- Part A: trailers -----------------------------------------------------
def iso_duration_seconds(text):
    """YouTube gives lengths like 'PT3M26S' or 'PT1H30M15S' → seconds."""
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", text)
    hours, minutes, seconds = (int(x) if x else 0 for x in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def is_trailer(title):
    low = title.lower()
    return "trailer" in low and not any(word in low for word in PROMO_WORDS)


def official_versions(items, main_id):
    """Keep the main trailer plus videos that look like the same trailer dubbed into another language."""
    main = next(v for v in items if v["id"] == main_id)
    main_len = iso_duration_seconds(main["contentDetails"]["duration"])
    keep = []
    for v in items:
        same_length = abs(iso_duration_seconds(v["contentDetails"]["duration"]) - main_len) <= main_len * DURATION_TOLERANCE
        if v["id"] == main_id or (is_trailer(v["snippet"]["title"]) and same_length):
            keep.append(v)
    return keep


def find_trailer_versions(film, key):
    """Return the raw videos.list items for every official trailer version of this film."""
    out_file = RAW_DIR / "trailers" / f"{film.film_id}.json"
    if out_file.exists():  # already collected on an earlier run → no quota spent
        saved = json.loads(out_file.read_text())
        return official_versions(saved["all_items"], film.main_trailer_video_id)

    main = youtube_get("videos", {"key": key, "part": "snippet", "id": film.main_trailer_video_id})
    snippet = main["items"][0]["snippet"]
    published = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))

    # Same channel, 1 day before to 3 days after the main trailer (language versions drop together)
    title_words = re.sub(r"\s*\(.*?\)|:", "", film.title)
    search = youtube_get("search", {
        "key": key, "part": "snippet", "type": "video", "maxResults": 25,
        "channelId": snippet["channelId"], "q": f"{title_words} trailer",
        "publishedAfter": (published - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "publishedBefore": (published + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    ids = {item["id"]["videoId"] for item in search["items"]}
    ids.add(film.main_trailer_video_id)  # search can miss it; we always keep the main one

    stats = youtube_get("videos", {"key": key, "part": "snippet,statistics,contentDetails",
                                   "id": ",".join(sorted(ids))})
    # Save EVERYTHING the API returned; the filter is applied when reading, so it can be changed
    # later without spending quota again.
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps({"film_id": film.film_id, "main_trailer": film.main_trailer_video_id,
                                    "search_raw": search, "all_items": stats["items"]}, ensure_ascii=False))
    return official_versions(stats["items"], film.main_trailer_video_id)


# --- Part B: comments -----------------------------------------------------
def pull_comments(film_id, video_id, key):
    """Page through ALL top-level comments of one video, saving each page. Resumable."""
    folder = COMMENTS_DIR / video_id
    folder.mkdir(parents=True, exist_ok=True)
    state_file = folder / "_state.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {"pages": 0, "next": None, "done": False}

    while not state["done"]:
        # Leave a little quota spare instead of running to the very last unit
        if youtube_daily_budget() - youtube_quota_today() <= UNITS_TO_KEEP_SPARE:
            print(f"  pausing {film_id}: only {UNITS_TO_KEEP_SPARE} units left today — re-run tomorrow to resume")
            return False

        params = {"key": key, "part": "snippet", "videoId": video_id, "maxResults": 100,
                  "order": "time", "textFormat": "plainText"}
        if state["next"]:
            params["pageToken"] = state["next"]
        page = youtube_get("commentThreads", params, pause_s=0.2)

        state["pages"] += 1
        (folder / f"page_{state['pages']:05d}.json").write_text(json.dumps(page, ensure_ascii=False))
        state["next"] = page.get("nextPageToken")
        state["done"] = state["next"] is None
        state_file.write_text(json.dumps(state))

        if state["pages"] % 50 == 0:
            print(f"  {film_id}: {state['pages']} pages ({youtube_quota_today()} units used today)")

    print(f"  {film_id}: complete, {state['pages']} pages")
    return True


def main():
    key = get_env("YT_API_KEY")
    films = pd.read_csv(DATA_MANUAL / "film_list.csv")

    # Optional: `python src/03_collect_youtube.py chhaava` collects one film only. This lets
    # several films download at the same time in separate processes; the quota guard's
    # file lock keeps their combined spending under the daily limit.
    if len(sys.argv) > 1:
        films = films[films.film_id == sys.argv[1]]
        if films.empty:
            raise SystemExit(f"Unknown film_id {sys.argv[1]}")

    try:
        print("Part A — trailer versions")
        for film in films.itertuples():
            items = find_trailer_versions(film, key)
            views = sum(int(v["statistics"].get("viewCount", 0)) for v in items)
            print(f"  {film.film_id:24} {len(items)} version(s), {views:>12,} views total")

        print("\nPart B — comments on main trailers")
        complete = 0
        for film in films.itertuples():
            if pull_comments(film.film_id, film.main_trailer_video_id, key):
                complete += 1
        print(f"\nComments complete for {complete}/{len(films)} films")

    except YouTubeQuotaExceeded as e:
        print(f"\nSTOPPED: {e}\nEverything so far is saved. Re-run after the quota resets to continue.")

    log_source_access("YouTube Data API v3", "https://www.googleapis.com/youtube/v3/",
                      "videos.list + search.list + commentThreads.list", f"{len(films)} films")
    print_youtube_quota()


if __name__ == "__main__":
    main()
