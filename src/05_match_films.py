"""
Step 05 — Give every source the same film key (film_id), using fuzzy title matching.

The same film is spelled differently in every source:
    Wikipedia page   "Saiyaara (film)"
    TMDb             "Kantara - A Legend: Chapter 1"
    YouTube          "RAID 2 (TRAILER): Ajay D | Riteish D | ..."
    Google Trends    "Dhurandhar 2"
    Yearly table     "Dhurandhar"   ← a DIFFERENT film (the 2025 prequel) that must NOT match

How:
  1. normalise() both sides: lowercase, drop "(film)" / "(2025)", "official trailer", language tags,
     everything after "|", punctuation.
  2. Score against every canonical title with rapidfuzz (0–100):
       - token_sort_ratio for sources that give a FULL title (extra words lower the score)
       - partial_ratio for sources where the title sits inside a longer string (YouTube) or is a
         short form (Trends), because there we ask "does the title appear in here?"
  3. Decide: >= 95 accept · 70–94 a human must confirm (manual step M9) · < 70 reject.

Outputs: data/clean/film_matches.csv (every decision), data/manual/match_review.csv (rows for M9)
"""

import os
import re
import sys

import pandas as pd
from rapidfuzz import fuzz

sys.path.insert(0, os.path.dirname(__file__))
from utils import DATA_CLEAN, DATA_INTERIM, DATA_MANUAL, log_cleaning, reset_cleaning_log_for_stage  # noqa: E402

STAGE = "05_match_films"
ACCEPT = 95
REVIEW = 70

LANGUAGE_TAGS = ["hindi", "telugu", "tamil", "kannada", "malayalam", "english"]
NOISE_PHRASES = ["official trailer", "trailer", "teaser", "official"]


def normalise(title):
    """'RAID 2 (TRAILER): Ajay D | Riteish D' → 'raid 2'   ·   'Saiyaara (film)' → 'saiyaara'"""
    t = title.lower()
    t = t.split("|")[0]                       # YouTube: cast/crew names come after "|"
    t = re.sub(r"\(.*?\)", " ", t)            # "(film)", "(2025 film)", "(trailer)", "(malayalam)"
    for phrase in NOISE_PHRASES:
        t = t.replace(phrase, " ")
    t = re.sub(r"[^a-z0-9 ]", " ", t)         # punctuation: ":" "-" "!" etc.
    words = [w for w in t.split() if w not in LANGUAGE_TAGS]
    return " ".join(words)


def best_match(source_title, canon, method):
    """Score one source title against every canonical film; return (film_id, score)."""
    norm = normalise(source_title)
    scorer = fuzz.token_sort_ratio if method == "token_sort_ratio" else fuzz.partial_ratio
    scores = {row.film_id: scorer(norm, row.norm) for row in canon.itertuples()}
    film_id = max(scores, key=scores.get)
    return norm, film_id, round(scores[film_id], 1)


def decide(score):
    if score >= ACCEPT:
        return "accept"
    if score >= REVIEW:
        return "needs_review"
    return "reject"


def collect_titles(films):
    """Every title string, from every source, that needs to be tied to a film_id."""
    rows = []
    for f in films.itertuples():
        rows.append(("wikipedia_page", f.wiki_page, f.film_id, "token_sort_ratio"))
        rows.append(("google_trends_term", f.trends_search_term, f.film_id, "partial_ratio"))

    for r in pd.read_csv(DATA_INTERIM / "tmdb_films.csv").itertuples():
        rows.append(("tmdb", r.title, r.film_id, "token_sort_ratio"))

    for r in pd.read_csv(DATA_INTERIM / "yt_trailers.csv").itertuples():
        rows.append(("youtube_trailer", r.video_title, r.film_id, "partial_ratio"))

    # The yearly table has NO film_id of its own — this is the source that truly needs matching.
    for r in pd.read_csv(DATA_INTERIM / "wiki_year_grossers.csv").itertuples():
        rows.append(("wiki_yearly_table", r.Title, None, "token_sort_ratio"))

    return pd.DataFrame(rows, columns=["source", "source_title", "collected_for", "method"])


def apply_confirmations(matches):
    """Rows a human confirmed in M9 (data/manual/match_confirmations.csv: source, source_title, confirmed yes/no)."""
    path = DATA_MANUAL / "match_confirmations.csv"
    if not path.exists():
        return matches, 0
    conf = pd.read_csv(path)
    merged = matches.merge(conf[["source", "source_title", "confirmed"]], on=["source", "source_title"], how="left")
    yes = (merged.decision == "needs_review") & (merged.confirmed.str.lower() == "yes")
    no = (merged.decision == "needs_review") & (merged.confirmed.str.lower() == "no")
    merged.loc[yes, "decision"] = "accept (human confirmed)"
    merged.loc[no, "decision"] = "reject (human rejected)"
    return merged.drop(columns=["confirmed"]), int(yes.sum() + no.sum())


def main():
    reset_cleaning_log_for_stage(STAGE)
    films = pd.read_csv(DATA_MANUAL / "film_list.csv")
    canon = films[["film_id", "title"]].copy()
    canon["norm"] = canon["title"].apply(normalise)

    titles = collect_titles(films)
    results = [best_match(t.source_title, canon, t.method) for t in titles.itertuples()]
    titles[["normalised", "best_film_id", "score"]] = pd.DataFrame(results, index=titles.index)
    titles["decision"] = titles["score"].apply(decide)

    # Sanity check: where we already know which film a title was collected for, the matcher
    # must agree. A disagreement would mean the matcher is wrong, so we stop.
    known = titles.dropna(subset=["collected_for"])
    wrong = known[(known.best_film_id != known.collected_for) & (known.decision != "reject")]
    if not wrong.empty:
        print(wrong.to_string())
        raise SystemExit("Matcher disagrees with known film ids — fix normalise() before continuing")

    titles, confirmed = apply_confirmations(titles)
    DATA_CLEAN.mkdir(parents=True, exist_ok=True)
    titles.to_csv(DATA_CLEAN / "film_matches.csv", index=False)

    review = titles[titles.decision == "needs_review"]
    review[["source", "source_title", "normalised", "best_film_id", "score"]].assign(confirmed="").to_csv(
        DATA_MANUAL / "match_review.csv", index=False)

    pd.set_option("display.width", 200)
    print(titles.groupby(["source", "decision"]).size().to_string())
    print(f"\nScores below {ACCEPT} (need a human look):")
    print(titles[titles.score < ACCEPT][["source", "source_title", "best_film_id", "score", "decision"]].to_string(index=False))

    counts = titles.decision.value_counts()
    log_cleaning(STAGE, "Same film spelled differently across 5 sources (e.g. TMDb 'Kantara - A Legend: Chapter 1', YouTube 'RAID 2 (TRAILER): Ajay D | ...')",
                 len(titles), "Normalised titles (lowercase, removed brackets, 'trailer', language tags, text after '|', punctuation) then rapidfuzz-scored against the 10 canonical titles",
                 "A shared film_id is what lets us JOIN trailers, box office, comments and trends")
    log_cleaning(STAGE, f"Fuzzy scores below {ACCEPT}", int((titles.score < ACCEPT).sum()),
                 f"{REVIEW}–{ACCEPT - 1}: sent to a human (M9, data/manual/match_review.csv); below {REVIEW}: rejected",
                 "A wrong join silently corrupts every later number, so uncertain matches are checked by a person")
    rejected = titles[titles.decision.str.startswith("reject")]
    log_cleaning(STAGE, "Yearly grossing table row 'Dhurandhar' (the 2025 prequel) looks like 'Dhurandhar: The Revenge'",
                 int((rejected.source == "wiki_yearly_table").sum()),
                 "Rejected by token_sort_ratio (extra words lower the score), not joined to any film",
                 "partial_ratio would have scored it 100 and joined the wrong film's ₹1,350 crore gross")
    print(f"\nDecisions: {counts.to_dict()} | human confirmations applied: {confirmed}")


if __name__ == "__main__":
    main()
