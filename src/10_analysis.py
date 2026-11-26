"""
Step 10 — Analysis: normalise, correlate, build and test a Buzz Index, check for bot-like bursts.

Per film we compute "buzz" features:
  total_views         all official trailer versions (CAUTION: today's count, includes post-release views)
  like_ratio          likes ÷ views on the main trailer
  comments_7d         comments in the first 7 days after the main trailer (true trailer-week, from timestamps)
  comments_per_hour   comments per hour over the first 72 h (velocity)
  sentiment_7d        mean VADER score of first-7-day comments, ignoring comments VADER can't read (score 0)
and the outcome: first_weekend_per_day (₹ crore per day of the first weekend).

Methods, and why:
  - Spearman rank correlation, not Pearson: with n = 10 and one huge film (Dhurandhar: The Revenge),
    Pearson would be driven by that one point. Spearman only uses the ORDER of films.
  - z-scores (normalisation) put views (millions) and crores on one scale for the charts and the index.
  - Buzz Index = weighted sum of z-scored features. Weights are learned from the OTHER films only
    (leave-one-out), so each film is predicted by an index that never saw it. Honest test, even with n = 10.
"""

import hashlib
import os
import re
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, os.path.dirname(__file__))
from utils import DATA_CLEAN, OUT_TABLES, log_cleaning, reset_cleaning_log_for_stage  # noqa: E402

STAGE = "10_analysis"
FEATURES = ["total_views", "like_ratio", "comments_7d", "comments_per_hour", "sentiment_7d"]
OUTCOME = "first_weekend_per_day"
FLAGGED = ["housefull_5", "sitaare_zameen_par"]   # weekend figure not clearly worldwide


def zscore(series):
    """(value − mean) ÷ standard deviation → 0 = average film, +1 = one SD above average."""
    return (series - series.mean()) / series.std(ddof=0)


def build_features():
    films = pd.read_csv(DATA_CLEAN / "films.csv")
    trailers = pd.read_csv(DATA_CLEAN / "trailers.csv", parse_dates=["publish_ts"])
    comments = pd.read_csv(DATA_CLEAN / "comments.csv", usecols=["film_id", "published_ts", "vader_compound", "text_clean"],
                           parse_dates=["published_ts"])
    box = pd.read_csv(DATA_CLEAN / "box_office.csv")

    main = trailers[trailers.is_main_trailer].set_index("film_id")
    f = films.set_index("film_id")[["title_clean", "language"]].copy()
    f["is_regional"] = f.language != "Hindi"
    f["total_views"] = trailers.groupby("film_id")["views"].sum()
    f["like_ratio"] = main["likes"] / main["views"]

    comments = comments.join(main["publish_ts"], on="film_id")
    comments["hours_after"] = (comments.published_ts - comments.publish_ts).dt.total_seconds() / 3600
    week = comments[(comments.hours_after >= 0) & (comments.hours_after < 24 * 7)]
    f["comments_7d"] = week.groupby("film_id").size()
    f["comments_per_hour"] = comments[(comments.hours_after >= 0) & (comments.hours_after < 72)].groupby("film_id").size() / 72
    readable = week[week.vader_compound != 0]
    f["sentiment_7d"] = readable.groupby("film_id")["vader_compound"].mean()
    f["sentiment_n"] = readable.groupby("film_id").size()

    weekend = box[box.metric == OUTCOME].set_index("film_id")["value_cr"]
    f[OUTCOME] = weekend
    f["lifetime_gross"] = box[(box.metric == "lifetime_gross_ww") & (box.source == "Wikipedia infobox")].set_index("film_id")["value_cr"]

    # Normalised copies (z-scores). Views are log-scaled first: 16M and 130M differ by ~8×,
    # and on a raw scale one film would dominate.
    f["z_log_views"] = zscore(np.log10(f.total_views))
    f["z_outcome"] = zscore(f[OUTCOME])
    for col in FEATURES:
        f[f"z_{col}"] = zscore(np.log10(f[col]) if col in ["total_views", "comments_7d", "comments_per_hour"] else f[col])
    f["minmax_outcome"] = (f[OUTCOME] - f[OUTCOME].min()) / (f[OUTCOME].max() - f[OUTCOME].min())

    pre = comments[comments.hours_after < 0]
    log_cleaning(STAGE, "Comments time-stamped BEFORE their trailer's publish time", len(pre),
                 "Excluded from trailer-week features", "Impossible timestamps (clock/timezone edge cases) cannot be trailer-week reactions")
    log_cleaning(STAGE, "Views (millions), crores and sentiment (−1..+1) are on very different scales", len(f),
                 "z-scored every feature and the outcome; views and comment counts log10-scaled first",
                 "Lets one chart and one index combine them; log stops the 130M-view film dominating")
    return f.reset_index(), week


def correlations(f):
    rows = []
    subsets = {"all films": f, "excluding flagged weekend figures": f[~f.film_id.isin(FLAGGED)]}
    for label, data in subsets.items():
        for feat in FEATURES:
            rho, p = spearmanr(data[feat], data[OUTCOME])
            rows.append({"subset": label, "feature": feat, "n": len(data), "spearman_rho": round(rho, 3), "p_value": round(p, 3)})
    corr = pd.DataFrame(rows)

    # Does sentiment add anything beyond views? Partial Spearman: correlate the RANK residuals
    # of sentiment and outcome after removing what views explain.
    ranks = f[["total_views", "sentiment_7d", OUTCOME]].rank()
    def residual(y, x):
        slope, intercept = np.polyfit(x, y, 1)
        return y - (slope * x + intercept)
    r_sent = residual(ranks.sentiment_7d, ranks.total_views)
    r_out = residual(ranks[OUTCOME], ranks.total_views)
    partial_rho = np.corrcoef(r_sent, r_out)[0, 1]
    corr = pd.concat([corr, pd.DataFrame([{"subset": "all films", "feature": "sentiment_7d | controlling for views (partial)",
                                           "n": len(f), "spearman_rho": round(partial_rho, 3), "p_value": float("nan")}])])
    corr.to_csv(OUT_TABLES / "correlations.csv", index=False)
    return corr


def buzz_weights(train):
    """Weight each z-scored feature by its Spearman ρ with the outcome on the TRAINING films (negative → 0)."""
    weights = {}
    for feat in FEATURES:
        rho, _ = spearmanr(train[f"z_{feat}"], train[OUTCOME])
        weights[feat] = max(rho, 0.0)
    total = sum(weights.values()) or 1.0
    return {k: v / total for k, v in weights.items()}


def buzz_index_loo(f):
    """Leave-one-out: for each film, learn weights on the other 9, then score the held-out film."""
    rows = []
    for held_out in f.film_id:
        train = f[f.film_id != held_out]
        w = buzz_weights(train)
        scores = sum(w[feat] * f[f"z_{feat}"] for feat in FEATURES)
        f_scores = f.assign(buzz=scores)
        median_outcome = train[OUTCOME].median()
        median_buzz = f_scores[f_scores.film_id != held_out].buzz.median()
        film = f_scores[f_scores.film_id == held_out].iloc[0]
        rows.append({
            "held_out_film": held_out,
            "buzz_index": round(film.buzz, 3),
            "predicted_rank_of_10": int(f_scores.buzz.rank(ascending=False)[film.name]),
            "actual_rank_of_10": int(f[OUTCOME].rank(ascending=False)[film.name]),
            "called_above_median": bool(film.buzz > median_buzz),
            "actually_above_median": bool(film[OUTCOME] > median_outcome),
            **{f"w_{k}": round(v, 2) for k, v in w.items()},
        })
    loo = pd.DataFrame(rows)
    loo["call_correct"] = loo.called_above_median == loo.actually_above_median
    loo["rank_error"] = (loo.predicted_rank_of_10 - loo.actual_rank_of_10).abs()
    loo.to_csv(OUT_TABLES / "buzz_index_loo.csv", index=False)
    return loo


def bot_check(week):
    """Bursts of near-identical comments: same normalised text posted ≥ 5 times within one hour for one film."""
    w = week.copy()
    norm = w.text_clean.str.lower().str.replace(r"[^\w\s]", "", regex=True).str.replace(r"\s+", " ", regex=True).str.strip()
    w["text_hash"] = norm.map(lambda t: hashlib.md5(t.encode()).hexdigest()[:12])
    w["hour"] = w.published_ts.dt.floor("h")
    w["words"] = norm.str.split().str.len()
    # Very short comments ("first", "🔥") repeat naturally; only look at comments of 5+ words
    long = w[w.words >= 5]
    bursts = long.groupby(["film_id", "text_hash", "hour"]).agg(copies=("text_hash", "size"), example=("text_clean", "first")).reset_index()
    bursts = bursts[bursts.copies >= 5].sort_values("copies", ascending=False)
    summary = (long.groupby("film_id").size().rename("comments_5plus_words").to_frame()
               .join(bursts.groupby("film_id").copies.sum().rename("comments_in_bursts")).fillna(0))
    summary["share_in_bursts"] = (summary.comments_in_bursts / summary.comments_5plus_words).round(4)
    summary.to_csv(OUT_TABLES / "bot_check_by_film.csv")
    bursts.head(30).to_csv(OUT_TABLES / "bot_check_top_bursts.csv", index=False)
    log_cleaning(STAGE, "Possible paid/bot buzz: the same 5+-word comment posted 5+ times within one hour",
                 int(bursts.copies.sum()), "Flagged (not deleted); share per film reported in bot_check_by_film.csv",
                 "Deleting needs proof; flagging lets us show whether any film's buzz is inflated")
    return summary, bursts


def main():
    reset_cleaning_log_for_stage(STAGE)
    pd.set_option("display.width", 220)
    f, week = build_features()
    f.to_csv(OUT_TABLES / "film_features.csv", index=False)
    print(f[["film_id", "language", "total_views", "like_ratio", "comments_7d", "comments_per_hour", "sentiment_7d", OUTCOME]].round(4).to_string(index=False))

    corr = correlations(f)
    print("\n" + corr.to_string(index=False))

    loo = buzz_index_loo(f)
    print("\n" + loo[["held_out_film", "buzz_index", "predicted_rank_of_10", "actual_rank_of_10", "call_correct", "rank_error"]].to_string(index=False))
    print(f"\nLeave-one-out: correct above/below-median calls {loo.call_correct.sum()}/{len(loo)}, mean rank error {loo.rank_error.mean():.1f}")

    summary, bursts = bot_check(week)
    print("\n" + summary.to_string())
    if not bursts.empty:
        print(bursts.head(5)[["film_id", "copies", "example"]].to_string(index=False))


if __name__ == "__main__":
    main()
