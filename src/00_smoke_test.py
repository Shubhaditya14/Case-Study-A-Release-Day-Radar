"""
Phase 1 check: does every source actually return data for ONE film?

Run:  .venv/bin/python src/00_smoke_test.py
It tests Wikipedia, TMDb and YouTube for the test film below and prints
PASS / FAIL / SKIP for each. Nothing is saved — this is only a connection test.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from utils import http_get_json, add_youtube_quota  # noqa: E402

TEST_FILM = "Chhaava"
WIKI_API = "https://en.wikipedia.org/w/api.php"


def test_wikipedia():
    # MediaWiki API, action=parse returns the page's rendered HTML inside JSON.
    # Wikipedia asks API users to send a descriptive User-Agent with contact info.
    contact = os.getenv("WIKI_CONTACT", "student-project")
    headers = {"User-Agent": f"ReleaseDayRadar/0.1 (course project; {contact})"}
    params = {"action": "parse", "page": TEST_FILM, "prop": "text", "format": "json", "redirects": 1}
    data = http_get_json(WIKI_API, params=params, headers=headers)
    html = data["parse"]["text"]["*"]
    has_box_office = "Box office" in html
    return f"page '{data['parse']['title']}', {len(html):,} chars of HTML, infobox 'Box office' found: {has_box_office}"


def test_tmdb():
    key = os.getenv("TMDB_API_KEY", "").strip()
    if not key:
        return None
    params = {"api_key": key, "query": TEST_FILM, "year": 2025}
    data = http_get_json("https://api.themoviedb.org/3/search/movie", params=params)
    if not data["results"]:
        raise RuntimeError("TMDb returned 0 results")
    top = data["results"][0]
    return f"{data['total_results']} results; top = '{top['title']}' ({top['release_date']}), tmdb_id {top['id']}"


def test_youtube():
    key = os.getenv("YT_API_KEY", "").strip()
    if not key:
        return None
    # videos.list costs 1 unit. We use a well-known public video ID just to prove the key works;
    # finding each film's real trailer ID happens in Phase 2.
    params = {"key": key, "part": "snippet,statistics", "id": "dQw4w9WgXcQ"}
    data = http_get_json("https://www.googleapis.com/youtube/v3/videos", params=params)
    used = add_youtube_quota(1)
    item = data["items"][0]
    return f"key works; test video has {int(item['statistics']['viewCount']):,} views (quota used today: {used})"


def run(name, fn):
    try:
        result = fn()
        if result is None:
            print(f"SKIP  {name}: key not in .env yet")
        else:
            print(f"PASS  {name}: {result}")
    except Exception as e:  # we want to see every failure, not stop at the first one
        print(f"FAIL  {name}: {e}")


if __name__ == "__main__":
    run("Wikipedia (MediaWiki API)", test_wikipedia)
    run("TMDb API", test_tmdb)
    run("YouTube Data API v3", test_youtube)
