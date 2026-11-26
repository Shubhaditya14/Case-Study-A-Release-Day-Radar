"""
Step 04 — Flatten nested JSON into flat tables with pd.json_normalize.

json_normalize turns nested keys into columns joined by dots, e.g.
    {"snippet": {"topLevelComment": {"snippet": {"publishedAt": "..."}}}}
becomes one column called  snippet.topLevelComment.snippet.publishedAt

Inputs : data/raw/tmdb/*.json, data/raw/youtube/trailers/*.json, data/raw/youtube/comments/*/page_*.json
Outputs: data/interim/tmdb_films.csv, yt_trailers.csv, yt_comments.csv
         outputs/tables/json_normalize_example.md   (before/after example for the report)

PRIVACY: author name, author channel id/URL and profile image are dropped HERE, before anything
leaves data/raw/. data/raw/ is gitignored, so usernames never reach the repo.
"""

import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import DATA_INTERIM, DATA_MANUAL, DATA_RAW, OUT_TABLES, log_cleaning, reset_cleaning_log_for_stage  # noqa: E402

# Re-use step 03's "which videos are official trailer versions" rule, so both steps agree.
# (importlib is needed only because the file name starts with a digit.)
import importlib  # noqa: E402
official_versions = importlib.import_module("03_collect_youtube").official_versions

STAGE = "04_flatten_json"

# Comment fields that identify a person → never leave data/raw/
PRIVATE_COLUMNS = [
    "snippet.topLevelComment.snippet.authorDisplayName",
    "snippet.topLevelComment.snippet.authorProfileImageUrl",
    "snippet.topLevelComment.snippet.authorChannelUrl",
    "snippet.topLevelComment.snippet.authorChannelId.value",
    "snippet.channelId",
]


def flatten_tmdb():
    rows = []
    for path in sorted((DATA_RAW / "tmdb").glob("*.json")):
        record = json.loads(path.read_text())
        details = record["tmdb"]
        # Lists inside the JSON (genres, cast) do not fit in one cell, so we join them as text
        flat = pd.json_normalize(details, max_level=1)
        flat["genres"] = ", ".join(g["name"] for g in details["genres"])
        flat["top_cast"] = ", ".join(c["name"] for c in details["credits"]["cast"][:3])
        flat["film_id"] = record["film_id"]
        rows.append(flat)
    df = pd.concat(rows, ignore_index=True)
    keep = ["film_id", "id", "title", "original_title", "original_language", "release_date",
            "runtime", "budget", "revenue", "genres", "top_cast", "vote_average", "vote_count"]
    return df[keep].rename(columns={"id": "tmdb_id"})


def flatten_trailers():
    rows = []
    rejected = 0
    for path in sorted((DATA_RAW / "youtube" / "trailers").glob("*.json")):
        record = json.loads(path.read_text())
        kept = official_versions(record["all_items"], record["main_trailer"])
        rejected += len(record["all_items"]) - len(kept)
        flat = pd.json_normalize(kept)
        flat["film_id"] = record["film_id"]
        flat["is_main_trailer"] = flat["id"] == record["main_trailer"]
        rows.append(flat)
    df = pd.concat(rows, ignore_index=True)
    keep = {"film_id": "film_id", "id": "youtube_video_id", "is_main_trailer": "is_main_trailer",
            "snippet.title": "video_title", "snippet.channelTitle": "channel_title",
            "snippet.publishedAt": "publish_ts_raw", "contentDetails.duration": "duration_raw",
            "statistics.viewCount": "views_raw", "statistics.likeCount": "likes_raw",
            "statistics.commentCount": "comment_count_raw"}
    # Columns can be missing if a channel hides likes/comments; add them empty so the table shape is fixed
    for col in keep:
        if col not in df.columns:
            df[col] = None
    return df[list(keep)].rename(columns=keep), rejected


def flatten_comments(films):
    """Read every saved page of every main trailer and flatten the comment items."""
    frames = []
    example = None
    for film in films.itertuples():
        folder = DATA_RAW / "youtube" / "comments" / film.main_trailer_video_id
        for page_path in sorted(folder.glob("page_*.json")):
            items = json.loads(page_path.read_text()).get("items", [])
            if not items:
                continue
            if example is None:
                example = items[0]
            flat = pd.json_normalize(items)
            flat["film_id"] = film.film_id
            frames.append(flat)
    df = pd.concat(frames, ignore_index=True)

    present_private = [c for c in PRIVATE_COLUMNS if c in df.columns]
    df = df.drop(columns=present_private)

    keep = {"film_id": "film_id",
            "snippet.topLevelComment.id": "comment_id",
            "snippet.videoId": "youtube_video_id",
            "snippet.topLevelComment.snippet.publishedAt": "published_ts_raw",
            "snippet.topLevelComment.snippet.textOriginal": "text_raw",
            "snippet.topLevelComment.snippet.likeCount": "like_count",
            "snippet.totalReplyCount": "reply_count"}
    return df[list(keep)].rename(columns=keep), example, present_private


def write_example(example, flat_comments):
    """Before/after json_normalize example for the report (author fields redacted)."""
    shown = json.loads(json.dumps(example))
    top = shown["snippet"]["topLevelComment"]["snippet"]
    for field in ["authorDisplayName", "authorProfileImageUrl", "authorChannelUrl", "authorChannelId"]:
        if field in top:
            top[field] = "«removed for privacy»"
    shown["snippet"].pop("channelId", None)
    after = flat_comments[flat_comments.comment_id == example["snippet"]["topLevelComment"]["id"]]

    text = ["# json_normalize: before and after", "",
            "**Before** — one YouTube comment as the API returns it (nested JSON, author fields redacted here):", "",
            "```json", json.dumps(shown, indent=2, ensure_ascii=False), "```", "",
            "**After** — the same comment as one flat row (author columns dropped entirely):", "",
            after.to_markdown(index=False), ""]
    (OUT_TABLES / "json_normalize_example.md").write_text("\n".join(text))


def main():
    reset_cleaning_log_for_stage(STAGE)
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    OUT_TABLES.mkdir(parents=True, exist_ok=True)
    films = pd.read_csv(DATA_MANUAL / "film_list.csv")

    tmdb = flatten_tmdb()
    trailers, rejected_videos = flatten_trailers()
    comments, example, dropped = flatten_comments(films)

    tmdb.to_csv(DATA_INTERIM / "tmdb_films.csv", index=False)
    trailers.to_csv(DATA_INTERIM / "yt_trailers.csv", index=False)
    comments.to_csv(DATA_INTERIM / "yt_comments.csv", index=False)
    write_example(example, comments)

    print(f"tmdb_films: {len(tmdb)} rows | yt_trailers: {len(trailers)} rows | yt_comments: {len(comments):,} rows")
    print(comments.groupby("film_id").size().to_string())

    log_cleaning(STAGE, "YouTube comment JSON contains author names, channel ids and profile URLs",
                 len(comments), f"Dropped {len(dropped)} identifying columns during flattening: {', '.join(c.split('.')[-1] if not c.endswith('.value') else 'authorChannelId' for c in dropped)}",
                 "Brief's ground rule: protect people. Usernames never leave data/raw/, which is gitignored")
    log_cleaning(STAGE, "Channel search returned promo videos (launch events, speeches, Shorts, 30 s cut-downs) whose titles contain 'trailer'",
                 rejected_videos, "Kept only the main trailer plus videos with 'trailer' in the title, no promo words, and length within 10% of the main trailer",
                 "Dubbed language versions are the same edit, so same length; counting promos would inflate views for films with busy channels (Peddi had 16 'trailer' videos, 1 real)")
    log_cleaning(STAGE, "TMDb genres and cast are lists inside JSON, which do not fit in one table cell",
                 len(tmdb), "Joined genre names into one comma-separated text column; kept only top-3 billed cast",
                 "One row per film keeps the films table simple; we describe genre/cast, we don't model them")


if __name__ == "__main__":
    main()
