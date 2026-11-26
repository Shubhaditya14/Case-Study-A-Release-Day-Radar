"""
Step 12 — Build the evidence tables the brief asks for, from what the pipeline actually produced.

  outputs/tables/source_register.csv  URL, access date, method, terms of use, note
                                       (dates come from data/raw/source_access_log.csv, written by each collector)
  outputs/tables/data_inventory.csv   every field we use: type (nominal/ordinal/discrete/continuous) and shape
  outputs/tables/v_profile.csv        Volume (rows, MB per source), Variety (formats), Velocity (comments per hour,
                                       Trends rise and decay) — all measured, none estimated
  outputs/tables/velocity_by_film.csv per-film velocity detail
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import DATA_CLEAN, DATA_MANUAL, DATA_RAW, OUT_TABLES, SOURCE_LOG, trailer_start_times  # noqa: E402

TERMS = {
    "Wikipedia": "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use (API etiquette: https://www.mediawiki.org/wiki/API:Etiquette)",
    "TMDb": "https://www.themoviedb.org/api-terms-of-use",
    "YouTube Data API v3": "https://developers.google.com/youtube/terms/api-services-terms-of-service",
    "Frankfurter (ECB reference rates)": "https://frankfurter.dev (open-source API serving European Central Bank reference rates)",
    "Google Trends": "https://policies.google.com/terms",
    "IMDb 50K labelled reviews": "Research dataset, Maas et al. (2011), https://ai.stanford.edu/~amaas/data/sentiment/ (copy from Homework 1.2 / Kaggle)",
}
NOTES = {
    "Wikipedia": "Box-office infobox + text via MediaWiki API (HTML inside JSON); descriptive User-Agent; 1 s between calls; revision ids saved",
    "TMDb": "Genre, runtime, language, cast; free developer key; credited as the data source",
    "YouTube Data API v3": "Trailer stats + all top-level comments of main trailers; quota hard-capped at 10,000 units/day; usernames dropped before leaving data/raw",
    "Frankfurter (ECB reference rates)": "One USD→INR rate to convert the only USD box-office figure",
    "Google Trends": "Daily India search interest, exported by hand (pytrends is unreliable); values are relative 0–100 per export",
    "IMDb 50K labelled reviews": "Labelled practice corpus: validates VADER and lifts the Spark job above 50,000 rows",
}


def folder_mb(path):
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / 1e6, 1)


def source_register():
    log = pd.read_csv(SOURCE_LOG)
    log["accessed_utc"] = pd.to_datetime(log["accessed_utc"])
    reg = (log.groupby("source")
           .agg(url=("url", "first"), method=("method", lambda m: " ; ".join(sorted(set(m)))),
                first_access=("accessed_utc", "min"), last_access=("accessed_utc", "max"))
           .reset_index())

    # Manual / local sources have no collector log: use the files' own modification dates
    trends_files = sorted(DATA_MANUAL.glob("trends_*.csv"))
    trends_time = pd.to_datetime([f.stat().st_mtime for f in trends_files], unit="s", utc=True)
    imdb_time = pd.to_datetime((DATA_MANUAL / "imdb_50k.csv").stat().st_mtime, unit="s", utc=True)
    extra = pd.DataFrame([
        {"source": "Google Trends", "url": "https://trends.google.com/trends/explore (geo=IN, daily)",
         "method": "Manual CSV export, one search term per film", "first_access": trends_time.min(), "last_access": trends_time.max()},
        {"source": "IMDb 50K labelled reviews", "url": "local file data/manual/imdb_50k.csv",
         "method": "Local CSV (Homework 1.2)", "first_access": imdb_time, "last_access": imdb_time},
    ])
    reg = pd.concat([reg, extra], ignore_index=True)
    reg["access_date"] = reg["first_access"].dt.strftime("%Y-%m-%d")
    reg["terms_of_use"] = reg["source"].map(TERMS)
    reg["note"] = reg["source"].map(NOTES)
    reg = reg[["source", "url", "access_date", "method", "terms_of_use", "note"]]
    reg.to_csv(OUT_TABLES / "source_register.csv", index=False)
    return reg


def data_inventory():
    rows = [
        # field, table, example, measurement type, shape, source
        ("film_id", "all tables", "kantara_chapter_1", "nominal", "structured", "created in step 05"),
        ("title_clean", "films", "Kantara: Chapter 1", "nominal", "structured", "film list / Wikipedia"),
        ("language", "films", "Kannada", "nominal", "structured", "Wikipedia infobox"),
        ("genre", "films", "Action, Drama, Fantasy", "nominal", "semi-structured", "TMDb JSON"),
        ("runtime_min", "films", "169", "discrete", "structured", "Wikipedia infobox"),
        ("release_date", "films", "2025-10-02", "interval (date)", "structured", "Wikipedia infobox"),
        ("budget_cr", "films", "110.0", "continuous", "structured", "Wikipedia infobox"),
        ("tmdb_id", "films", "1083637", "nominal (an id, not a quantity)", "semi-structured", "TMDb JSON"),
        ("first_weekend_ww", "box_office", "330.0", "continuous", "unstructured → structured", "Wikipedia article text"),
        ("first_weekend_per_day", "box_office", "82.5", "continuous", "derived", "step 06"),
        ("lifetime_gross_ww", "box_office", "851.0", "continuous", "structured", "Wikipedia infobox + yearly table"),
        ("weekend_days", "film list", "4", "discrete", "structured", "release weekday"),
        ("scope_flag", "box_office.note", "domestic_only", "nominal", "structured", "step 06"),
        ("youtube_video_id", "trailers", "TMQUFhWm8C0", "nominal", "semi-structured", "YouTube JSON"),
        ("is_main_trailer", "trailers", "1", "nominal (binary)", "semi-structured", "step 03"),
        ("publish_ts", "trailers", "2025-09-22 12:44:00 IST", "interval (timestamp)", "semi-structured", "YouTube JSON"),
        ("views", "trailers", "23925371", "discrete (count)", "semi-structured", "YouTube JSON"),
        ("likes", "trailers", "512345", "discrete (count)", "semi-structured", "YouTube JSON"),
        ("comment_count", "trailers", "20869", "discrete (count)", "semi-structured", "YouTube JSON"),
        ("comment text (text_clean)", "comments", "Goosebumps!! 🔥", "unstructured", "unstructured", "YouTube JSON → text"),
        ("published_ts", "comments", "2025-01-22 17:20:11 IST", "interval (timestamp)", "semi-structured", "YouTube JSON"),
        ("length", "comments", "15", "discrete", "derived", "step 06"),
        ("vader_compound", "comments", "0.6369", "continuous (−1 to +1)", "derived", "step 07"),
        ("vader label (pos/neg)", "validation", "positive", "nominal", "derived", "step 07"),
        ("interest", "trends_daily", "100", "ordinal-like relative index (0–100, scaled per export)", "structured", "Google Trends CSV"),
        ("date", "trends_daily", "2025-10-03", "interval (date)", "structured", "Google Trends CSV"),
        ("IMDb review text", "imdb_50k", "One of the best films...", "unstructured", "unstructured", "IMDb 50K CSV"),
        ("IMDb sentiment label", "imdb_50k", "positive", "nominal (binary)", "structured", "IMDb 50K CSV"),
        ("match score", "film_matches", "79.1", "continuous (0–100)", "derived", "step 05"),
        ("box-office trade rank", "wiki yearly table", "2", "ordinal", "structured", "Wikipedia yearly list"),
    ]
    inv = pd.DataFrame(rows, columns=["field", "table", "example", "measurement_type", "shape", "source"])
    inv.to_csv(OUT_TABLES / "data_inventory.csv", index=False)
    return inv


def velocity():
    comments = pd.read_csv(DATA_CLEAN / "comments.csv", usecols=["film_id", "published_ts"], parse_dates=["published_ts"])
    main = trailer_start_times()   # earlier of API publish time and first comment
    films = pd.read_csv(DATA_CLEAN / "films.csv", parse_dates=["release_date"]).set_index("film_id")
    trends = pd.read_csv(DATA_CLEAN / "trends_daily.csv", parse_dates=["date"])

    rows = []
    for film_id, group in comments.groupby("film_id"):
        hours = (group.published_ts - main[film_id]).dt.total_seconds() / 3600
        first72 = hours[(hours >= 0) & (hours < 72)]
        per_hour = first72.floordiv(1).value_counts()
        t = trends[trends.film_id == film_id].sort_values("date")
        peak = t.loc[t.interest.idxmax()]
        after = t[t.date > peak.date]
        below_half = after[after.interest < peak.interest / 2]
        rows.append({
            "film_id": film_id,
            "comments_total": len(group),
            "comments_first_72h": len(first72),
            "share_in_first_72h": round(len(first72) / len(group), 3),
            "comments_first_hour": int((hours.between(0, 1, inclusive="left")).sum()),
            "peak_comments_per_hour": int(per_hour.max()),
            "comments_per_hour_72h": round(len(first72) / 72, 1),
            "trends_days_trailer_to_peak": (peak.date - main[film_id].normalize()).days,
            "trends_peak_days_after_release": (peak.date - films.loc[film_id, "release_date"]).days,
            "trends_days_peak_to_half": (below_half.date.min() - peak.date).days if not below_half.empty else None,
        })
    vel = pd.DataFrame(rows)
    vel.to_csv(OUT_TABLES / "velocity_by_film.csv", index=False)
    return vel


def v_profile(vel):
    clean_rows = {name: len(pd.read_csv(DATA_CLEAN / f"{name}.csv", usecols=[0])) for name in
                  ["films", "trailers", "box_office", "comments", "trends_daily"]}
    imdb_rows = len(pd.read_csv(DATA_MANUAL / "imdb_50k.csv", usecols=[1]))
    trends_mb = round(sum(f.stat().st_size for f in DATA_MANUAL.glob("trends_*.csv")) / 1e6, 3)
    spark = pd.read_csv(OUT_TABLES / "spark_stage_counts.csv").set_index("stage")["rows"]
    spark_input, spark_words = int(spark["1c union"]), int(spark["4a words (exploded)"])
    title_strings = len(pd.read_csv(DATA_CLEAN / "film_matches.csv"))
    rows = [
        ("Volume", "YouTube raw JSON (stats + comment pages)", folder_mb(DATA_RAW / "youtube"), "MB"),
        ("Volume", "YouTube comment pages downloaded", len(list((DATA_RAW / "youtube" / "comments").rglob("page_*.json"))), "files"),
        ("Volume", "Trailer comments after cleaning", clean_rows["comments"], "rows"),
        ("Volume", "Wikipedia raw JSON", folder_mb(DATA_RAW / "wikipedia"), "MB"),
        ("Volume", "TMDb raw JSON", folder_mb(DATA_RAW / "tmdb"), "MB"),
        ("Volume", "Google Trends CSVs", trends_mb, "MB"),
        ("Volume", "Google Trends daily rows", clean_rows["trends_daily"], "rows"),
        ("Volume", "IMDb 50K corpus", imdb_rows, "rows"),
        ("Volume", "IMDb 50K corpus size", round((DATA_MANUAL / "imdb_50k.csv").stat().st_size / 1e6, 1), "MB"),
        ("Volume", "Spark job input (comments + IMDb, tagged by source)", spark_input, "rows (1c union in spark_stage_counts.csv)"),
        ("Volume", "Spark job word rows after explode", spark_words, "rows (4a in spark_stage_counts.csv)"),
        ("Variety", "Formats", 4, "HTML-in-JSON (Wikipedia), JSON (YouTube, TMDb, Frankfurter), CSV (Trends, IMDb), free text (comments, reviews)"),
        ("Variety", "Sources", 6, "Wikipedia, TMDb, YouTube, Google Trends, Frankfurter, IMDb 50K"),
        ("Variety", "Title strings from 5 sources tied to the 10 film_ids", title_strings, "strings (data/clean/film_matches.csv)"),
        ("Velocity", "Median share of a trailer's comments posted in its first 72 h", round(vel.share_in_first_72h.median(), 3), "share"),
        ("Velocity", "Highest comments/hour in any single hour (first 72 h)", int(vel.peak_comments_per_hour.max()), "comments/hour"),
        ("Velocity", "Mean comments/hour over first 72 h (median film)", round(vel.comments_per_hour_72h.median(), 1), "comments/hour"),
        ("Velocity", "Google Trends peak, days after release (median)", float(vel.trends_peak_days_after_release.median()), "days"),
        ("Velocity", "Google Trends: days from peak until interest halves (median)", float(vel.trends_days_peak_to_half.median()), "days"),
    ]
    vp = pd.DataFrame(rows, columns=["v", "measure", "value", "unit_or_detail"])
    vp.to_csv(OUT_TABLES / "v_profile.csv", index=False)
    return vp


def main():
    pd.set_option("display.width", 220); pd.set_option("display.max_colwidth", 70)
    print(source_register()[["source", "access_date", "method"]].to_string(index=False))
    print(f"\ndata_inventory: {len(data_inventory())} fields")
    vel = velocity()
    print("\n" + vel.to_string(index=False))
    print("\n" + v_profile(vel).to_string(index=False))


if __name__ == "__main__":
    main()
