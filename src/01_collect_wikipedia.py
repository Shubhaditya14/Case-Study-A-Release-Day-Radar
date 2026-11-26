"""
Step 01 — Collect box-office data from Wikipedia (structured source, HTML tables inside JSON).

For each film in data/manual/film_list.csv:
  1. Call the MediaWiki API (action=parse). It returns the page's HTML wrapped in JSON,
     plus the revision id, so we can say exactly which version of the page we used.
  2. Read the infobox with pandas.read_html  → release date, budget, box office, running time.
  3. Pull every sentence that mentions an opening/weekend and a money figure → candidates.
  4. Check the human-chosen first-weekend phrase (data/manual/first_weekend_phrases.csv)
     really appears in the page text. If it does not, we stop: no number is ever made up.

Also reads the "List of Indian films of 2025/2026" grossing tables (lifetime worldwide gross)
as a second, consistently formatted box-office table.

Outputs (data/interim/):
  wiki_infobox.csv           one row per film per infobox field (raw text, not yet cleaned)
  wiki_weekend_sentences.csv every candidate sentence, for transparency
  wiki_first_weekend_raw.csv the verified phrase per film (parsed into numbers in step 06)
  wiki_year_grossers.csv     rows of the yearly grossing tables that match our films
"""

import io
import json
import os
import re
import sys

import pandas as pd
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from utils import (DATA_INTERIM, DATA_MANUAL, DATA_RAW, log_source_access,  # noqa: E402
                   reset_cleaning_log_for_stage, log_cleaning, wiki_get)

RAW_DIR = DATA_RAW / "wikipedia"
STAGE = "01_collect_wikipedia"
YEAR_PAGES = ["List of Indian films of 2025", "List of Indian films of 2026"]

# Infobox fields we keep (everything else, like "Cinematography", is not needed for the question)
INFOBOX_FIELDS = ["Release date", "Running time", "Language", "Languages", "Budget", "Box office", "Country"]


def fetch_page(page, film_id):
    """Download one page through the MediaWiki API and save the untouched JSON."""
    data = wiki_get({"action": "parse", "page": page, "prop": "text|revid", "redirects": 1})
    if "error" in data:
        raise SystemExit(f"Wikipedia error for {page}: {data['error']['info']}")
    (RAW_DIR / f"{film_id}.json").write_text(json.dumps(data, ensure_ascii=False))
    return data["parse"]


def page_text(html):
    """HTML → plain text with citation markers like [12] removed and whitespace collapsed."""
    text = BeautifulSoup(html, "lxml").get_text(" ")
    text = re.sub(r"\[\s*\d+\s*\]", "", text)
    text = re.sub(r"\s+", " ", text)
    # Cut off the reference list: its citation titles also mention crores and would confuse us
    cut = text.find("References [ edit")
    return text[:cut] if cut > 0 else text


def read_infobox(html, film_id):
    """Use pandas.read_html on the infobox table and return long rows: film_id, field, value_raw."""
    tables = pd.read_html(io.StringIO(html), attrs={"class": "infobox vevent"})
    box = tables[0]
    box.columns = ["field", "value_raw"]
    box = box[box["field"].isin(INFOBOX_FIELDS)].copy()
    box.insert(0, "film_id", film_id)
    return box


def weekend_sentences(text, film_id):
    """Every sentence that talks about an opening/weekend AND contains a money figure."""
    rows = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        talks_opening = re.search(r"weekend|opening|first day|four-day|4 days", sentence, re.I)
        has_money = re.search(r"₹|crore|\$\s?\d", sentence)
        if talks_opening and has_money:
            rows.append({"film_id": film_id, "sentence": sentence.strip()})
    return rows


def read_year_grossers():
    """The yearly 'highest-grossing' tables: one consistent lifetime-gross figure per film."""
    frames = []
    for page in YEAR_PAGES:
        data = wiki_get({"action": "parse", "page": page, "prop": "text|revid", "redirects": 1})
        safe = page.lower().replace(" ", "_")
        (RAW_DIR / f"{safe}.json").write_text(json.dumps(data, ensure_ascii=False))
        tables = pd.read_html(io.StringIO(data["parse"]["text"]))
        # The first table that has a "Worldwide gross" column is the top-grossers table
        for table in tables:
            if "Worldwide gross" in [str(c) for c in table.columns]:
                table = table[["Rank", "Title", "Language", "Worldwide gross"]].copy()
                table["list_page"] = page
                table["revid"] = data["parse"]["revid"]
                frames.append(table)
                break
    return pd.concat(frames, ignore_index=True)


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    reset_cleaning_log_for_stage(STAGE)
    films = pd.read_csv(DATA_MANUAL / "film_list.csv")
    phrases = pd.read_csv(DATA_MANUAL / "first_weekend_phrases.csv")

    infobox_rows, sentence_rows, weekend_rows = [], [], []
    for film in films.itertuples():
        print(f"Wikipedia: {film.wiki_page}")
        parsed = fetch_page(film.wiki_page, film.film_id)
        html = parsed["text"]
        text = page_text(html)

        infobox_rows.append(read_infobox(html, film.film_id))
        sentence_rows.extend(weekend_sentences(text, film.film_id))

        # The anti-fabrication check: the chosen phrase must be in the page, word for word.
        phrase = phrases.loc[phrases.film_id == film.film_id, "phrase"].iloc[0]
        if phrase not in text:
            raise SystemExit(f"Phrase for {film.film_id} not found in Wikipedia revision {parsed['revid']}. "
                             "The page may have been edited — re-check data/manual/first_weekend_phrases.csv")
        weekend_rows.append({"film_id": film.film_id, "phrase": phrase, "revid": parsed["revid"],
                             "weekend_days": film.weekend_days, "scope_flag": film.scope_flag})

    infobox = pd.concat(infobox_rows, ignore_index=True)
    sentences = pd.DataFrame(sentence_rows)
    weekend = pd.DataFrame(weekend_rows)

    # Keep only the yearly-table rows that are our films (matching is done properly in step 05;
    # here a loose lowercase "contains" check is enough to keep the file small).
    grossers = read_year_grossers()
    wanted = films["title"].str.lower().str.replace(r"[^a-z0-9 ]", "", regex=True)
    titles = grossers["Title"].str.lower().str.replace(r"[^a-z0-9 ]", "", regex=True)
    grossers = grossers[titles.apply(lambda t: any(w[:12] in t or t in w for w in wanted))]

    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    infobox.to_csv(DATA_INTERIM / "wiki_infobox.csv", index=False)
    sentences.to_csv(DATA_INTERIM / "wiki_weekend_sentences.csv", index=False)
    weekend.to_csv(DATA_INTERIM / "wiki_first_weekend_raw.csv", index=False)
    grossers.to_csv(DATA_INTERIM / "wiki_year_grossers.csv", index=False)

    print(f"\ninfobox rows: {len(infobox)} | candidate sentences: {len(sentences)} | "
          f"verified weekend phrases: {len(weekend)}/{len(films)} | yearly-table matches: {len(grossers)}")

    # Cleaning-log entries with real counts
    log_cleaning(STAGE, "Wikipedia gives opening figures as free text in inconsistent forms (day vs weekend, worldwide vs India, ranges, USD)",
                 len(sentences), f"Saved all {len(sentences)} candidate sentences; one verified phrase per film chosen in data/manual/first_weekend_phrases.csv",
                 "No single regex picks the right figure on every page; a human choice that the script verifies word-for-word against the source is transparent and cannot invent numbers")
    no_budget = films.shape[0] - infobox[infobox.field == "Budget"].film_id.nunique()
    log_cleaning(STAGE, "Infobox has no Budget field for some films", no_budget,
                 "Kept films; budget left missing (NULL) for them",
                 "Budget is a confounder we describe, not our outcome — dropping films for it would shrink an already small n")

    log_source_access("Wikipedia", "https://en.wikipedia.org/w/api.php", "MediaWiki API action=parse + pandas.read_html",
                      f"{len(films)} film pages + {len(YEAR_PAGES)} yearly list pages; revision ids saved")


if __name__ == "__main__":
    main()
