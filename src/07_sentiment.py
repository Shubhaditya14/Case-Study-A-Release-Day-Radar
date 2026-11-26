"""
Step 07 — Sentiment with VADER: test it on labelled data FIRST, then use it on our comments.

Why VADER: it is a word list + rules built for short social-media text (it understands
"!!!", ALL CAPS, emojis like 😍 and "not good"). It needs no training data, which we don't have
for trailer comments.

Part A — validation on the IMDb 50K corpus (labelled positive / negative):
    compound >= 0.05 → predict "positive", otherwise "negative" (VADER's documented cut-off).
    Report accuracy, F1 and the confusion matrix.
Part B — score every cleaned trailer comment and add vader_compound to data/clean/comments.csv.
Part C — measure where VADER is blind on OUR data (Indian scripts, Hinglish → compound exactly 0).
"""

import os
import re
import sys

import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

sys.path.insert(0, os.path.dirname(__file__))
from utils import DATA_CLEAN, DATA_MANUAL, OUT_TABLES, log_cleaning, reset_cleaning_log_for_stage  # noqa: E402

STAGE = "07_sentiment"
POSITIVE_CUTOFF = 0.05

# Unicode blocks for the Indian scripts our comments use (VADER's word list is English-only)
INDIC_SCRIPTS = r"[ऀ-ॿ஀-௿ఀ-౿ಀ-೿ഀ-ൿ]"


def load_imdb():
    imdb = pd.read_csv(DATA_MANUAL / "imdb_50k.csv")
    start = len(imdb)

    dupes = imdb.duplicated(subset="review").sum()
    imdb = imdb.drop_duplicates(subset="review")
    log_cleaning(STAGE, "IMDb 50K contains exact duplicate review texts", int(dupes),
                 "Dropped repeats, kept first", "A duplicated review would be counted twice in accuracy/F1 and in the Spark job")

    html = imdb["review"].str.contains("<br").sum()
    imdb["review"] = imdb["review"].str.replace(r"<br\s*/?>", " ", regex=True)
    log_cleaning(STAGE, "IMDb reviews contain HTML line breaks ('<br />')", int(html),
                 "Replaced with a space", "Markup is not language; it would show up as fake terms ('br') in the term counts")
    print(f"IMDb: {start:,} → {len(imdb):,} rows")
    return imdb


def validate_on_imdb(analyzer):
    imdb = load_imdb()
    print("Scoring IMDb reviews with VADER (takes a couple of minutes)...")
    imdb["vader_compound"] = imdb["review"].map(lambda t: analyzer.polarity_scores(t)["compound"])
    imdb["predicted"] = (imdb["vader_compound"] >= POSITIVE_CUTOFF).map({True: "positive", False: "negative"})

    acc = accuracy_score(imdb["sentiment"], imdb["predicted"])
    f1_pos = f1_score(imdb["sentiment"], imdb["predicted"], pos_label="positive")
    f1_macro = f1_score(imdb["sentiment"], imdb["predicted"], average="macro")
    cm = confusion_matrix(imdb["sentiment"], imdb["predicted"], labels=["positive", "negative"])

    results = pd.DataFrame([
        {"metric": "rows_scored", "value": len(imdb)},
        {"metric": "accuracy", "value": round(acc, 4)},
        {"metric": "f1_positive", "value": round(f1_pos, 4)},
        {"metric": "f1_macro", "value": round(f1_macro, 4)},
        {"metric": "true_pos (actual pos, predicted pos)", "value": int(cm[0, 0])},
        {"metric": "false_neg (actual pos, predicted neg)", "value": int(cm[0, 1])},
        {"metric": "false_pos (actual neg, predicted pos)", "value": int(cm[1, 0])},
        {"metric": "true_neg (actual neg, predicted neg)", "value": int(cm[1, 1])},
    ])
    results.to_csv(OUT_TABLES / "vader_validation.csv", index=False)
    print(results.to_string(index=False))
    return acc, f1_macro, cm


def score_comments(analyzer):
    comments = pd.read_csv(DATA_CLEAN / "comments.csv")
    print(f"Scoring {len(comments):,} trailer comments...")
    comments["vader_compound"] = comments["text_clean"].map(lambda t: analyzer.polarity_scores(str(t))["compound"])

    indic = comments["text_clean"].str.contains(INDIC_SCRIPTS, regex=True)
    zero = comments["vader_compound"] == 0
    # Latin-script comments that VADER scores exactly 0 are mostly Hinglish / names / hashtags
    latin_zero = zero & ~indic

    blind = (comments.assign(indic=indic, zero=zero)
             .groupby("film_id")
             .agg(comments=("comment_id", "size"), share_indic_script=("indic", "mean"), share_vader_zero=("zero", "mean"),
                  mean_compound=("vader_compound", "mean")).round(3))
    blind.to_csv(OUT_TABLES / "vader_blind_spots_by_film.csv")
    print(blind.to_string())

    log_cleaning(STAGE, "Comments written in Indian scripts (Devanagari, Telugu, Tamil, Kannada, Malayalam) — VADER cannot read them",
                 int(indic.sum()), "Kept in the data (they count for velocity) but their VADER score is 0; share reported per film",
                 "Dropping them would bias velocity against regional films; translating 300k comments is out of scope")
    log_cleaning(STAGE, "Latin-script comments that VADER scores exactly 0 (Hinglish, names, hashtags, emojis-only)",
                 int(latin_zero.sum()), "Kept; reported as VADER's blind-spot share; analysis also uses mean sentiment of non-zero comments",
                 "Treating 'no known words' as 'neutral' would pull every film's mean towards 0")

    comments.to_csv(DATA_CLEAN / "comments.csv", index=False)
    return comments


def main():
    reset_cleaning_log_for_stage(STAGE)
    analyzer = SentimentIntensityAnalyzer()
    acc, f1_macro, cm = validate_on_imdb(analyzer)
    log_cleaning(STAGE, "VADER is a generic tool — is it accurate enough on film text?", int(cm.sum()),
                 f"Validated on labelled IMDb reviews before use: accuracy {acc:.3f}, macro-F1 {f1_macro:.3f}",
                 "Using a sentiment score without checking it on labelled data would be guesswork")
    score_comments(analyzer)


if __name__ == "__main__":
    main()
