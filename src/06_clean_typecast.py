"""
Step 06 — Clean and type-cast everything into the five final tables (data/clean/).

The main type-casting problems, and what we do:
  "₹797.34–809 crore[b]"            → 803.17   (strip footnotes, range → midpoint, in ₹ crore)
  "est. ₹242.8 crore[3]"             → 242.8    (keep, note "estimate")
  "₹30−40 crore"                     → 35.0     (Unicode minus "−" used as a range dash)
  "1,25,00,000"                      → 1.25     (Indian lakh/crore digit grouping, rupees → crore)
  "50 lakh"                          → 0.5      (1 crore = 100 lakh)
  "over $80 million"                 → USD × release-date rate ÷ 1 crore (rate from Frankfurter/ECB API)
  "14 February 2025"                 → datetime 2025-02-14
  "2025-01-22T11:45:04Z" (UTC)       → 2025-01-22 17:15:04 IST
  "81728371" (count stored as text)  → int 81728371
  "<1" (Google Trends)               → 0.5

Every decision is written to outputs/cleaning_log.csv with the real number of rows affected.
"""

import json
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import (DATA_CLEAN, DATA_INTERIM, DATA_MANUAL, DATA_RAW, http_get_json,  # noqa: E402
                   log_cleaning, log_source_access, reset_cleaning_log_for_stage)

STAGE = "06_clean_typecast"
IST = "Asia/Kolkata"
FX_API = "https://api.frankfurter.dev/v1"


# --- Money parsing ----------------------------------------------------------
def strip_noise(text):
    """Remove footnotes [b] / [12], Wikipedia's own '(US$17 million)' conversions, and 'est.'."""
    t = re.sub(r"\[\s*\w+\s*\]", "", str(text))
    t = re.sub(r"\(US\$[^)]*\)", "", t)
    t = t.replace("est.", "")
    return t


def parse_indian_digits(text):
    """'1,25,00,000' (rupees, Indian grouping) → 1.25 crore. Commas are just separators either way."""
    rupees = float(text.replace(",", ""))
    return rupees / 1e7


def parse_money_to_crore(text, usd_rate=None):
    """
    Turn one money string into ₹ crore. Returns (value, low, high, note).
    A range becomes its midpoint; the note records what was done so the cleaning log can explain it.
    """
    t = strip_noise(text)
    notes = []
    if re.search(r"\best\.", str(text)):          # "est." only — not the "est" inside "milestone"
        notes.append("estimate")

    # US dollars: "$80 million" — only convertible if we have a rate for that date
    usd = re.search(r"\$\s*([\d.,]+)\s*(million|billion)", t, re.I)
    if usd and "₹" not in t:
        if usd_rate is None:
            return None, None, None, "USD figure, no rate given"
        amount = float(usd.group(1).replace(",", "")) * (1e6 if usd.group(2).lower() == "million" else 1e9)
        value = amount * usd_rate / 1e7
        return round(value, 2), None, None, f"converted from US${usd.group(1)} {usd.group(2)} at ₹{usd_rate}/USD"

    # Plain rupees with Indian digit grouping and no unit word: "₹1,25,00,000"
    plain = re.fullmatch(r"\s*₹?\s*(\d{1,3}(?:,\d{2})+,\d{3})\s*", t)
    if plain:
        return round(parse_indian_digits(plain.group(1)), 2), None, None, "Indian digit grouping (rupees → crore)"

    # Numbers followed (eventually) by "crore" or "lakh"
    unit = "lakh" if re.search(r"\blakh", t, re.I) and not re.search(r"crore", t, re.I) else "crore"
    to_crore = 0.01 if unit == "lakh" else 1.0
    # Range written as "157 crore – 164 crore", "797.34–809", or "30−40" (Unicode minus)
    numbers = re.findall(r"\d[\d,]*(?:\.\d+)?", t)
    numbers = [float(n.replace(",", "")) for n in numbers]
    if not numbers:
        return None, None, None, "no number found"
    is_range = bool(re.search(r"\d\s*(?:crore)?\s*[–—−-]\s*₹?\s*\d", t))
    if is_range and len(numbers) >= 2:
        low, high = numbers[0] * to_crore, numbers[1] * to_crore
        notes.append(f"range {numbers[0]:g}–{numbers[1]:g} → midpoint")
        return round((low + high) / 2, 2), low, high, "; ".join(notes)
    if unit == "lakh":
        notes.append("lakh → crore")
    if re.search(r"\bover\s*[₹$]", t, re.I):     # "over ₹100 crore" — not "₹91.83 crore over its weekend"
        notes.append("'over' = lower bound")
    return round(numbers[0] * to_crore, 2), None, None, "; ".join(notes)


# --- Small helpers ----------------------------------------------------------
def to_ist(series):
    """ISO-8601 UTC strings from YouTube → timezone-naive IST datetimes (MySQL DATETIME has no zone)."""
    return pd.to_datetime(series, utc=True).dt.tz_convert(IST).dt.tz_localize(None)


def count_to_int(series):
    """Counts arrive as text ('81728371'); missing means the channel hid them → keep as NULL, not 0."""
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def usd_inr_rate(day):
    """USD→INR reference rate (European Central Bank, via the free Frankfurter API) for one date."""
    data = http_get_json(f"{FX_API}/{day}", params={"from": "USD", "to": "INR"})
    (DATA_RAW / "fx").mkdir(parents=True, exist_ok=True)
    (DATA_RAW / "fx" / f"usd_inr_{day}.json").write_text(json.dumps(data))
    log_source_access("Frankfurter (ECB reference rates)", f"{FX_API}/{day}?from=USD&to=INR", "REST API (JSON)",
                      f"USD→INR rate for {day}: {data['rates']['INR']}")
    return data["rates"]["INR"]


# --- Table builders ---------------------------------------------------------
def build_films(films, infobox, tmdb):
    box = infobox.pivot_table(index="film_id", columns="field", values="value_raw", aggfunc="first")

    out = films[["film_id", "title", "language"]].rename(columns={"title": "title_clean"}).set_index("film_id")
    out["release_date"] = pd.to_datetime(box["Release date"], format="%d %B %Y")
    out["runtime_wiki"] = box["Running time"].str.extract(r"(\d+)")[0].astype(int)

    budgets = []
    for film_id, text in box["Budget"].items():
        if pd.isna(text) or "combined" in str(text).lower():
            budgets.append((film_id, None))
        else:
            budgets.append((film_id, parse_money_to_crore(text)[0]))
    out["budget_cr"] = pd.Series(dict(budgets))

    tm = tmdb.set_index("film_id")
    out["genre"] = tm["genres"]
    out["tmdb_id"] = tm["tmdb_id"]
    out["runtime_tmdb"] = tm["runtime"]
    out["release_date_tmdb"] = pd.to_datetime(tm["release_date"])
    out = out.reset_index()

    # --- cleaning-log entries for films ---
    combined = box["Budget"].fillna("").str.contains("combined", case=False).sum()
    log_cleaning(STAGE, "Budget given as text ranges (e.g. '₹90–130 crore[a]', 'est. ₹30−40 crore[3][4]') with footnotes and a Unicode minus sign",
                 int(box["Budget"].notna().sum()), "Stripped footnotes/'est.', treated '–' and '−' as range dashes, took the midpoint in ₹ crore",
                 "A single number per film is needed for SQL and charts; the midpoint is the least biased point in a published range")
    log_cleaning(STAGE, "Budget missing (Kantara: Chapter 1) or shared with another film (Dhurandhar: The Revenge 'combined with part 1')",
                 int(out["budget_cr"].isna().sum()), "Set budget_cr to NULL; films kept",
                 f"Halving a combined budget would invent a number ({combined} combined); budget is a described confounder, not our outcome")
    diff_rt = (out.runtime_wiki - out.runtime_tmdb).abs()
    log_cleaning(STAGE, "Running time differs between Wikipedia and TMDb", int((diff_rt > 0).sum()),
                 f"Used Wikipedia's runtime (biggest gap {int(diff_rt.max())} min); TMDb kept for comparison only",
                 "Wikipedia cites the censor-board certificate for most films; TMDb is user-edited. One rule for all films")
    diff_date = (out.release_date - out.release_date_tmdb).dt.days
    log_cleaning(STAGE, "TMDb release date is 1 day earlier than Wikipedia for some films", int((diff_date != 0).sum()),
                 "Used Wikipedia's theatrical release date", "TMDb often records paid-preview / overseas dates; the screen decision is about the Indian theatrical opening")

    out["runtime_min"] = out["runtime_wiki"]
    return out[["film_id", "title_clean", "language", "genre", "runtime_min", "release_date", "budget_cr", "tmdb_id"]]


def build_box_office(films_clean, infobox, weekend_raw, year_grossers, matches, usd_rate):
    rows = []
    for w in weekend_raw.itertuples():
        value, low, high, note = parse_money_to_crore(w.phrase, usd_rate=usd_rate)
        flag = "" if w.scope_flag == "ok" else f"flag: {w.scope_flag}"
        days = int(w.weekend_days)
        rows.append((w.film_id, "first_weekend_ww", value, "Wikipedia film page text",
                     "; ".join(part for part in [note, flag] if part)))
        rows.append((w.film_id, "first_weekend_per_day", round(value / days, 2), "derived",
                     "; ".join(part for part in [f"first_weekend_ww ÷ {days} days", flag] if part)))

    gross = infobox[infobox.field == "Box office"]
    for g in gross.itertuples():
        value, low, high, note = parse_money_to_crore(g.value_raw)
        rows.append((g.film_id, "lifetime_gross_ww", value, "Wikipedia infobox", note))

    # The yearly table has no film_id — use only the matches step 05 accepted
    ok = matches[(matches.source == "wiki_yearly_table") & matches.decision.str.startswith("accept")]
    ok = ok[["source_title", "best_film_id"]].drop_duplicates()
    yearly = year_grossers.merge(ok, left_on="Title", right_on="source_title")
    for y in yearly.itertuples():
        value, low, high, note = parse_money_to_crore(y._4)  # column "Worldwide gross"
        rows.append((y.best_film_id, "lifetime_gross_ww", value, "Wikipedia yearly list", note))

    bo = pd.DataFrame(rows, columns=["film_id", "metric", "value_cr", "source", "note"])

    # --- cleaning-log entries for box office ---
    ranges = bo.note.str.contains("range").sum()
    log_cleaning(STAGE, "Box-office figures published as ranges (e.g. '₹325–335 crore')", int(ranges),
                 "Converted to the midpoint; low/high kept in the note column", "Trade sources disagree; the midpoint avoids picking a side")
    usd = bo.note.str.contains("converted from US").sum()
    log_cleaning(STAGE, "Dhurandhar: The Revenge first weekend only published in USD ('over $80 million')", int(usd),
                 f"Converted at the ECB reference rate on its release date (₹{usd_rate}/USD, Frankfurter API) and noted it is a lower bound",
                 "Excluding it would lose the biggest film in the sample; converting at the release-date rate is reproducible and logged")
    days4 = (weekend_raw.weekend_days == 4).sum()
    log_cleaning(STAGE, "First weekends are 3 days (Friday release) for some films and 4 days (Thursday release) for others",
                 int(days4), "Added first_weekend_per_day = first-weekend gross ÷ number of days",
                 "Comparing a 4-day total with a 3-day total would favour Thursday releases by about a third")
    domestic = weekend_raw.scope_flag.isin(["domestic_only", "check_scope"]).sum()
    log_cleaning(STAGE, "Two weekend figures are not clearly worldwide (Housefull 5 domestic only; Sitaare Zameen Par scope not stated)",
                 int(domestic), "Kept, flagged in the note column, and tested with/without them in the analysis",
                 "Dropping them leaves n = 8; keeping them flagged lets us show whether they change the result")
    both = bo[bo.metric == "lifetime_gross_ww"].pivot_table(index="film_id", columns="source", values="value_cr")
    both = both.dropna()
    gap = ((both["Wikipedia infobox"] - both["Wikipedia yearly list"]).abs() / both["Wikipedia infobox"] * 100)
    log_cleaning(STAGE, "Lifetime gross appears in two Wikipedia places (film infobox and the yearly list)", len(both),
                 f"Kept both with their source; largest disagreement {gap.max():.1f}%",
                 "Two independent-looking tables that agree within a few % raises confidence in the figures")
    return bo


def build_trailers(trailers):
    t = trailers.copy()
    t["publish_ts"] = to_ist(t["publish_ts_raw"])
    t["views"] = count_to_int(t["views_raw"])
    t["likes"] = count_to_int(t["likes_raw"])
    t["comment_count"] = count_to_int(t["comment_count_raw"])
    log_cleaning(STAGE, "YouTube counts arrive as text and timestamps as ISO-8601 UTC strings", len(t),
                 "Counts → integers (hidden likes stay NULL, not 0); timestamps → IST datetimes",
                 "Text sorts '9' after '81728371'; UTC would put late-evening IST trailers on the wrong day")
    return t[["film_id", "youtube_video_id", "is_main_trailer", "publish_ts", "views", "likes", "comment_count"]]


def clean_comment_text(text):
    """Keep what VADER uses (case, punctuation, emojis); remove URLs and squeeze whitespace."""
    t = re.sub(r"https?://\S+", " ", str(text))
    t = re.sub(r"\s+", " ", t).strip()
    return t


def build_comments(comments):
    c = comments.copy()
    start = len(c)

    dupes = c.duplicated(subset="comment_id").sum()
    c = c.drop_duplicates(subset="comment_id")
    log_cleaning(STAGE, "Same comment id downloaded twice (pages shift while new comments arrive during paging)", int(dupes),
                 "Dropped repeats, kept first", "A comment counted twice would inflate velocity and that film's sentiment weight")

    c["text_clean"] = c["text_raw"].fillna("").map(clean_comment_text)
    urls = c["text_raw"].fillna("").str.contains(r"https?://").sum()
    log_cleaning(STAGE, "Comments contain URLs (links, timestamps to other videos)", int(urls),
                 "Removed URLs from text, kept the rest of the comment", "URLs carry no sentiment and distort length and term counts")

    empty = (c["text_clean"] == "").sum()
    c = c[c["text_clean"] != ""]
    log_cleaning(STAGE, "Empty comments after cleaning (only a link, or blank)", int(empty),
                 "Dropped", "Nothing to score; keeping them would add fake neutral sentiment")

    c["published_ts"] = to_ist(c["published_ts_raw"])
    c["length"] = c["text_clean"].str.len()
    print(f"comments: {start:,} → {len(c):,} rows")
    return c[["comment_id", "film_id", "published_ts", "text_clean", "length", "like_count", "reply_count"]]


def build_trends(films):
    frames = []
    below_one = 0
    for f in films.itertuples():
        raw = pd.read_csv(DATA_MANUAL / f"trends_{f.film_id}.csv", skiprows=2)
        raw.columns = ["date", "interest_raw"]
        below_one += (raw["interest_raw"].astype(str) == "<1").sum()
        raw["interest"] = pd.to_numeric(raw["interest_raw"].astype(str).replace("<1", "0.5"))
        raw["date"] = pd.to_datetime(raw["date"])
        raw["film_id"] = f.film_id
        frames.append(raw[["film_id", "date", "interest"]])
    trends = pd.concat(frames, ignore_index=True)
    log_cleaning(STAGE, "Google Trends writes very low interest as the text '<1'", int(below_one),
                 "Replaced with 0.5 (the middle of 0–1) and cast the column to numbers",
                 "0 would claim no searches at all; 1 overstates; 0.5 is the honest midpoint and too small to move any result")
    log_cleaning(STAGE, "Checked Trends files for missing days", 0,
                 "None missing across all 10 films — no fill needed", "Each export covered every day of its window")
    return trends


def write_spreadsheet_input(infobox, weekend_raw, year_grossers):
    """Every real ₹ string we collected, plus pandas' answer, for the Sheets-vs-pandas comparison (M10).
    The USD phrase is left out: it needs an exchange-rate lookup, which we only do in pandas."""
    money = infobox[infobox.field.isin(["Budget", "Box office"])]
    texts = (list(money.film_id + " | " + money.field) , list(money.value_raw))
    rows = [{"label": label, "raw_text": raw} for label, raw in zip(*texts)]
    rows += [{"label": f"{w.film_id} | first weekend", "raw_text": w.phrase}
             for w in weekend_raw.itertuples() if w.scope_flag != "usd_figure"]
    rows += [{"label": f"{y.Title} | yearly list", "raw_text": y._4} for y in year_grossers.itertuples()]
    sheet_in = pd.DataFrame(rows)
    sheet_in.insert(0, "id", range(1, len(sheet_in) + 1))
    sheet_in[["id", "label", "raw_text"]].to_csv(DATA_MANUAL / "spreadsheet_step_input.csv", index=False)

    sheet_in["pandas_crore"] = [parse_money_to_crore(t)[0] for t in sheet_in.raw_text]
    sheet_in.to_csv(DATA_CLEAN / "spreadsheet_step_pandas_answer.csv", index=False)


def main():
    reset_cleaning_log_for_stage(STAGE)
    films = pd.read_csv(DATA_MANUAL / "film_list.csv")
    infobox = pd.read_csv(DATA_INTERIM / "wiki_infobox.csv")
    weekend_raw = pd.read_csv(DATA_INTERIM / "wiki_first_weekend_raw.csv")
    year_grossers = pd.read_csv(DATA_INTERIM / "wiki_year_grossers.csv")
    tmdb = pd.read_csv(DATA_INTERIM / "tmdb_films.csv")
    trailers = pd.read_csv(DATA_INTERIM / "yt_trailers.csv")
    comments = pd.read_csv(DATA_INTERIM / "yt_comments.csv")
    matches = pd.read_csv(DATA_CLEAN / "film_matches.csv")

    # The only USD figure is Dhurandhar: The Revenge, so we need the rate on its release date
    usd_film = films[films.scope_flag == "usd_figure"].iloc[0]
    rate = usd_inr_rate(usd_film.release_date)

    films_clean = build_films(films, infobox, tmdb)
    box_office = build_box_office(films_clean, infobox, weekend_raw, year_grossers, matches, rate)
    trailers_clean = build_trailers(trailers)
    comments_clean = build_comments(comments)
    trends = build_trends(films)

    write_spreadsheet_input(infobox, weekend_raw, year_grossers)

    outputs = {"films": films_clean, "box_office": box_office, "trailers": trailers_clean,
               "comments": comments_clean, "trends_daily": trends}
    for name, df in outputs.items():
        df.to_csv(DATA_CLEAN / f"{name}.csv", index=False)
        print(f"data/clean/{name}.csv: {len(df):,} rows")

    pd.set_option("display.width", 220); pd.set_option("display.max_colwidth", 80)
    print(films_clean.to_string(index=False))
    print(box_office.sort_values(["metric", "film_id"]).to_string(index=False))


if __name__ == "__main__":
    main()
