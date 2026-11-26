"""
Phase 1: check which candidate films can actually be used.

A film is usable only if ALL THREE are true:
  1. Wikipedia has its page, a 2025–26 release date, and an opening-weekend figure in the text.
  2. TMDb finds it (gives us genre, runtime, language later).
  3. YouTube has an official trailer with comments switched on.

Output: data/manual/film_list_proposed.csv  (a human approves it in manual step M6)
Raw API answers are saved to data/raw/verify/ so nothing has to be re-downloaded.

Quota: one YouTube search.list (100 units) + one videos.list (1 unit) per film.
"""

import io
import json
import os
import re
import sys

import pandas as pd
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from utils import (DATA_MANUAL, DATA_RAW, get_env, http_get_json, log_source_access,  # noqa: E402
                   print_youtube_quota, wiki_get, youtube_get)

RAW_DIR = DATA_RAW / "verify"

# Candidate list: the prompt's suggestions, plus regional and 2026 films taken from
# Wikipedia's "List of Indian films of 2025/2026" grossing tables. We deliberately keep
# mid and weak performers (not just the top grossers) so opening weekends vary.
# (search term for Wikipedia, year, language we expect)
CANDIDATES = [
    ("Chhaava", 2025, "Hindi"),
    ("Saiyaara (film)", 2025, "Hindi"),
    ("Sitaare Zameen Par", 2025, "Hindi"),
    ("Housefull 5", 2025, "Hindi"),
    ("Raid 2 (film)", 2025, "Hindi"),
    ("War 2 (film)", 2025, "Hindi"),
    ("Thamma", 2025, "Hindi"),
    ("Jolly LLB 3", 2025, "Hindi"),
    ("Dhurandhar", 2025, "Hindi"),
    ("Coolie (2025 film)", 2025, "Tamil"),
    ("Kantara: Chapter 1", 2025, "Kannada"),
    ("Lokah Chapter 1: Chandra", 2025, "Malayalam"),
    ("L2: Empuraan", 2025, "Malayalam"),
    ("They Call Him OG", 2025, "Telugu"),
    ("Dhurandhar: The Revenge", 2026, "Hindi"),
    ("Border 2", 2026, "Hindi"),
    ("Jailer 2", 2026, "Tamil"),
    ("Peddi", 2026, "Telugu"),
]


def safe_name(title):
    """Turn 'Kantara: Chapter 1' into 'kantara_chapter_1' for file names."""
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


# --- Wikipedia ------------------------------------------------------------
def read_infobox(html):
    """Return the infobox as a dict {label: text}, e.g. {'Release date': '14 February 2025', ...}."""
    soup = BeautifulSoup(html, "lxml")
    box = soup.find("table", class_="infobox")
    fields = {}
    if box is None:
        return fields
    for row in box.find_all("tr"):
        label = row.find("th")
        value = row.find("td")
        if label and value:
            # Remove citation markers like [1] so values are readable
            for sup in value.find_all("sup"):
                sup.decompose()
            fields[label.get_text(" ", strip=True)] = value.get_text(" ", strip=True)
    return fields


def find_opening_weekend_sentences(html):
    """Return sentences from the article that mention an opening weekend and a crore/₹ figure."""
    text = BeautifulSoup(html, "lxml").get_text(" ")
    text = re.sub(r"\[\d+\]", "", text)  # drop [12]-style citations
    sentences = re.split(r"(?<=[.!?])\s+", text)
    hits = []
    for s in sentences:
        low = s.lower()
        if "opening weekend" in low and ("crore" in low or "₹" in s):
            hits.append(re.sub(r"\s+", " ", s).strip())
    return hits


def check_wikipedia(page):
    data = wiki_get({"action": "parse", "page": page, "prop": "text", "redirects": 1})
    if "error" in data:
        return {"wiki_ok": False, "wiki_note": data["error"]["info"]}

    (RAW_DIR / f"wiki_{safe_name(page)}.json").write_text(json.dumps(data))
    html = data["parse"]["text"]
    box = read_infobox(html)
    ow = find_opening_weekend_sentences(html)
    return {
        "wiki_ok": True,
        "wiki_title": data["parse"]["title"],
        "release_date_wiki": box.get("Release date", ""),
        "language_wiki": box.get("Language", box.get("Languages", "")),
        "budget_wiki": box.get("Budget", ""),
        "box_office_wiki": box.get("Box office", ""),
        "opening_weekend_found": len(ow) > 0,
        "opening_weekend_snippet": ow[0][:300] if ow else "",
    }


# --- TMDb -----------------------------------------------------------------
def check_tmdb(title, year, key):
    clean = re.sub(r"\s*\(.*?\)", "", title)  # "Raid 2 (film)" -> "Raid 2"
    data = http_get_json("https://api.themoviedb.org/3/search/movie",
                         params={"api_key": key, "query": clean, "year": year})
    (RAW_DIR / f"tmdb_{safe_name(title)}.json").write_text(json.dumps(data))
    if not data["results"]:
        return {"tmdb_ok": False}
    top = data["results"][0]
    return {
        "tmdb_ok": True,
        "tmdb_id": top["id"],
        "tmdb_title": top["title"],
        "tmdb_release_date": top.get("release_date", ""),
        "tmdb_original_language": top.get("original_language", ""),
    }


# --- YouTube --------------------------------------------------------------
def check_youtube(title, key):
    clean = re.sub(r"\s*\(.*?\)", "", title)
    search = youtube_get("search", {
        "key": key, "part": "snippet", "type": "video", "maxResults": 5,
        "q": f"{clean} official trailer",
    })
    (RAW_DIR / f"yt_search_{safe_name(title)}.json").write_text(json.dumps(search))

    ids = [item["id"]["videoId"] for item in search.get("items", [])]
    if not ids:
        return {"yt_ok": False}

    # One videos.list call (1 unit) gets stats for all 5 results at once.
    stats = youtube_get("videos", {"key": key, "part": "snippet,statistics", "id": ",".join(ids)})
    (RAW_DIR / f"yt_videos_{safe_name(title)}.json").write_text(json.dumps(stats))

    # Pick the most-viewed result whose title says "trailer" (fan edits and reaction videos rarely top this).
    videos = []
    for v in stats["items"]:
        videos.append({
            "id": v["id"],
            "title": v["snippet"]["title"],
            "channel": v["snippet"]["channelTitle"],
            "published": v["snippet"]["publishedAt"],
            "views": int(v["statistics"].get("viewCount", 0)),
            "comments": v["statistics"].get("commentCount"),  # missing = comments disabled
        })
    trailers = [v for v in videos if "trailer" in v["title"].lower()] or videos
    best = max(trailers, key=lambda v: v["views"])
    return {
        "yt_ok": True,
        "yt_video_id": best["id"],
        "yt_title": best["title"],
        "yt_channel": best["channel"],
        "yt_published": best["published"],
        "yt_views": best["views"],
        "yt_comment_count": best["comments"] if best["comments"] is not None else "DISABLED",
    }


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    tmdb_key = get_env("TMDB_API_KEY")
    yt_key = get_env("YT_API_KEY")

    rows = []
    for page, year, lang in CANDIDATES:
        print(f"Checking {page} ...")
        row = {"wiki_page": page, "expected_year": year, "expected_language": lang}
        row.update(check_wikipedia(page))
        row.update(check_tmdb(page, year, tmdb_key))
        row.update(check_youtube(page, yt_key))
        rows.append(row)

    df = pd.DataFrame(rows)
    out = DATA_MANUAL / "film_list_candidates_checked.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved {len(df)} rows to {out}")

    log_source_access("Wikipedia", "https://en.wikipedia.org/w/api.php", "MediaWiki API action=parse",
                      f"Phase 1 film verification, {len(df)} pages")
    log_source_access("TMDb", "https://api.themoviedb.org/3/search/movie", "REST API /search/movie",
                      f"Phase 1 film verification, {len(df)} searches")
    log_source_access("YouTube Data API v3", "https://www.googleapis.com/youtube/v3/search",
                      "search.list + videos.list", f"Phase 1 trailer lookup, {len(df)} films")
    print_youtube_quota()


if __name__ == "__main__":
    main()
