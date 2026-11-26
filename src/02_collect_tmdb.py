"""
Step 02 — Collect film metadata from TMDb (semi-structured source, JSON API).

For each film:
  1. /search/movie   → find the TMDb id (we search by title + release year).
  2. /movie/{id}?append_to_response=credits → genre, runtime, original language,
     release date and top-billed cast, in ONE call (append_to_response saves a request).

The JSON is saved untouched in data/raw/tmdb/. Flattening into tables happens in step 04.
"""

import json
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import DATA_MANUAL, DATA_RAW, get_env, http_get_json, log_source_access  # noqa: E402

RAW_DIR = DATA_RAW / "tmdb"
BASE = "https://api.themoviedb.org/3"


def search_movie(title, year, key):
    """Return the best TMDb search result for this title and year (or None)."""
    data = http_get_json(f"{BASE}/search/movie", params={"api_key": key, "query": title, "year": year})
    if not data["results"]:
        # Some titles only match without the year filter (e.g. dated differently on TMDb)
        data = http_get_json(f"{BASE}/search/movie", params={"api_key": key, "query": title})
    return data["results"][0] if data["results"] else None


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    key = get_env("TMDB_API_KEY")
    films = pd.read_csv(DATA_MANUAL / "film_list.csv")

    found = 0
    for film in films.itertuples():
        year = int(film.release_date[:4])
        # TMDb doesn't use Wikipedia's "(film)" disambiguation, so search on the plain title
        title = re.sub(r"\s*\(.*?\)", "", film.title)
        hit = search_movie(title, year, key)
        if hit is None:
            print(f"  NOT FOUND on TMDb: {film.title}")
            continue

        details = http_get_json(f"{BASE}/movie/{hit['id']}",
                                params={"api_key": key, "append_to_response": "credits"})
        # Keep our own film_id next to TMDb's answer so later steps know which film it is.
        record = {"film_id": film.film_id, "search_title": title, "tmdb": details}
        (RAW_DIR / f"{film.film_id}.json").write_text(json.dumps(record, ensure_ascii=False))
        found += 1
        print(f"TMDb: {film.title:26} → id {details['id']}, '{details['title']}', "
              f"{details.get('runtime')} min, {[g['name'] for g in details['genres']]}")

    print(f"\nTMDb records saved: {found}/{len(films)}")
    log_source_access("TMDb", f"{BASE}/movie/{{id}}", "REST API /search/movie + /movie/{id}?append_to_response=credits",
                      f"{found} films")


if __name__ == "__main__":
    main()
