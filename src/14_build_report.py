"""
Step 14 — Build report/report.md (and slides.md) from templates, filling every number and table
from files the pipeline produced. Nothing numeric is typed by hand into the report.

Template syntax:
    {{num:rho_views}}        → a number computed below from outputs/tables/*.csv
    {{table:cleaning_log}}   → a markdown table built from a CSV
    {{file:path}}            → the contents of a generated markdown file (e.g. SQL results)
Run:  .venv/bin/python src/14_build_report.py   (then `make report` converts to .docx/.pdf/.pptx)
"""

import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import DATA_CLEAN, OUT_TABLES, ROOT, CLEANING_LOG  # noqa: E402

REPORT_DIR = ROOT / "report"


def fmt(x, digits=2):
    if isinstance(x, (int,)) or (isinstance(x, float) and x.is_integer() and abs(x) >= 100):
        return f"{int(x):,}"
    return f"{x:.{digits}f}"


def numbers():
    n = {}
    corr = pd.read_csv(OUT_TABLES / "correlations.csv")
    def rho(feature, subset="all films"):
        return corr[(corr.feature == feature) & (corr.subset == subset)].iloc[0]
    for key, feat in [("views", "total_views"), ("c7", "comments_7d"), ("cph", "comments_per_hour"),
                      ("sent", "sentiment_7d"), ("like", "like_ratio")]:
        n[f"rho_{key}"] = fmt(rho(feat).spearman_rho)
        n[f"p_{key}"] = fmt(rho(feat).p_value)
        n[f"rho_{key}_8"] = fmt(rho(feat, "excluding flagged weekend figures").spearman_rho)
    n["partial_sent"] = fmt(corr[corr.feature.str.contains("partial")].iloc[0].spearman_rho)

    loo = pd.read_csv(OUT_TABLES / "buzz_index_loo.csv")
    n["loo_hits"] = str(int(loo.call_correct.sum()))
    n["loo_err"] = fmt(loo.rank_error.mean(), 1)
    n["loo_misses"] = ", ".join(loo[~loo.call_correct].held_out_film.str.replace("_", " ").str.title())

    vader = pd.read_csv(OUT_TABLES / "vader_validation.csv").set_index("metric")["value"]
    n["vader_acc"] = fmt(vader["accuracy"], 3)
    n["vader_f1"] = fmt(vader["f1_macro"], 3)
    n["vader_fp"] = f"{int(vader['false_pos (actual neg, predicted pos)']):,}"
    n["vader_fn"] = f"{int(vader['false_neg (actual pos, predicted neg)']):,}"
    n["imdb_rows"] = f"{int(vader['rows_scored']):,}"

    log = pd.read_csv(CLEANING_LOG)
    n["cleaning_n"] = str(len(log))
    n["comments_raw"] = f"{int(log[log.problem_found.str.contains('author names')].rows_affected.iloc[0]):,}"
    comments = pd.read_csv(DATA_CLEAN / "comments.csv", usecols=["vader_compound", "text_clean"])
    n["comments_clean"] = f"{len(comments):,}"
    n["share_zero"] = f"{(comments.vader_compound == 0).mean():.0%}"
    n["share_indic"] = f"{comments.text_clean.str.contains(r'[ऀ-ൿ]', regex=True).mean():.0%}"

    vp = pd.read_csv(OUT_TABLES / "v_profile.csv").set_index("measure")["value"]
    n["yt_mb"] = fmt(vp["YouTube raw JSON (stats + comment pages)"], 0)
    n["comment_pages"] = f"{int(vp['YouTube comment pages downloaded']):,}"
    n["spark_in"] = f"{int(vp['Spark job input (comments + IMDb, tagged by source)']):,}"
    n["spark_words"] = f"{int(vp['Spark job word rows after explode']):,}"
    share_key = "Median share of a trailer's comments posted in its first 72 h"
    n["median_share72"] = f"{vp[share_key]:.0%}"
    n["peak_hour"] = f"{int(vp['Highest comments/hour in any single hour (first 72 h)']):,}"
    n["trends_half"] = fmt(vp["Google Trends: days from peak until interest halves (median)"], 0)
    n["title_strings"] = str(int(vp["Title strings from 5 sources tied to the 10 film_ids"]))

    q4 = pd.read_csv(OUT_TABLES / "sql_q4.csv").set_index("film_group")
    n["sent_hindi"] = fmt(q4.loc["Hindi", "mean_vader_nonzero"], 2)
    n["sent_regional"] = fmt(q4.loc["Regional", "mean_vader_nonzero"], 2)
    q7 = pd.read_csv(OUT_TABLES / "sql_q7.csv").set_index("film_group")
    n["wk_hindi"] = fmt(q7.loc["Hindi", "avg_first_weekend_per_day_cr"], 1)
    n["wk_regional"] = fmt(q7.loc["Regional", "avg_first_weekend_per_day_cr"], 1)
    n["views_hindi"] = fmt(q7.loc["Hindi", "avg_trailer_views_millions"], 1)
    n["views_regional"] = fmt(q7.loc["Regional", "avg_trailer_views_millions"], 1)

    bots = pd.read_csv(OUT_TABLES / "bot_check_by_film.csv").set_index("film_id")
    n["bot_raid"] = f"{bots.loc['raid_2', 'share_in_bursts']:.1%}"
    n["bot_others_max"] = f"{bots.drop('raid_2').share_in_bursts.max():.1%}"
    pre = pd.read_csv(OUT_TABLES / "prepublish_duplicates.csv")
    raid_pre = pre[(pre.film_id == "raid_2") & (pre.window == "before official publish")].iloc[0]
    after = pre[pre.window == "after official publish"].share_repeated_5plus
    n["raid_pre_n"] = f"{int(raid_pre.comments):,}"
    n["raid_pre_share"] = f"{raid_pre.share_repeated_5plus:.1%}"
    n["after_min"] = f"{after.min():.0%}"
    n["after_max"] = f"{after.max():.0%}"
    loo_raid = pd.read_csv(OUT_TABLES / "buzz_index_loo.csv").set_index("held_out_film").loc["raid_2"]
    n["raid_pred_rank"] = str(int(loo_raid.predicted_rank_of_10))
    n["raid_actual_rank"] = str(int(loo_raid.actual_rank_of_10))

    top = pd.read_csv(OUT_TABLES / "spark_top_terms.csv")
    n["sitaare_terms"] = ", ".join(top[top.film_id == "sitaare_zameen_par"].term.head(6))

    sheet = OUT_TABLES / "spreadsheet_vs_pandas.csv"
    if sheet.exists():
        s = pd.read_csv(sheet)
        n["sheet_agree"] = f"{int(s.agree.sum())}/{len(s)}"
    else:
        n["sheet_agree"] = "[[TODO-HUMAN: run M10, then `make report` fills this]]"
    return n


def md_table(df):
    return df.to_markdown(index=False)


def tables():
    t = {}
    t["data_inventory"] = md_table(pd.read_csv(OUT_TABLES / "data_inventory.csv"))
    vp = pd.read_csv(OUT_TABLES / "v_profile.csv")
    vp["value"] = vp["value"].map(lambda v: "" if pd.isna(v) else (f"{v:,.0f}" if v >= 100 else f"{v:g}"))
    t["v_profile"] = md_table(vp)
    log = pd.read_csv(CLEANING_LOG)
    t["cleaning_log_short"] = md_table(log[["id", "stage", "problem_found", "rows_affected"]])
    t["cleaning_log"] = md_table(log)
    t["source_register"] = md_table(pd.read_csv(OUT_TABLES / "source_register.csv"))
    t["spark_counts"] = md_table(pd.read_csv(OUT_TABLES / "spark_stage_counts.csv"))
    t["vader"] = md_table(pd.read_csv(OUT_TABLES / "vader_validation.csv"))
    t["blind"] = md_table(pd.read_csv(OUT_TABLES / "vader_blind_spots_by_film.csv"))
    corr = pd.read_csv(OUT_TABLES / "correlations.csv")
    t["correlations"] = md_table(corr)
    loo = pd.read_csv(OUT_TABLES / "buzz_index_loo.csv")
    t["loo"] = md_table(loo[["held_out_film", "buzz_index", "predicted_rank_of_10", "actual_rank_of_10", "call_correct"]])
    t["prepublish"] = md_table(pd.read_csv(OUT_TABLES / "prepublish_duplicates.csv"))
    t["mysql_counts"] = md_table(pd.read_csv(OUT_TABLES / "mysql_row_counts.csv"))
    top = pd.read_csv(OUT_TABLES / "spark_top_terms.csv")
    t["top_terms"] = md_table(top.groupby("film_id").term.apply(lambda s: ", ".join(s)).reset_index(name="top 10 terms (stopwords removed)"))
    sheet = OUT_TABLES / "spreadsheet_vs_pandas.csv"
    t["sheet_compare"] = md_table(pd.read_csv(sheet)[["id", "raw_text", "pandas_crore", "sheet_crore", "agree"]]) if sheet.exists() \
        else "[[TODO-HUMAN: complete manual step M10; `make report` then inserts the 36-row comparison here]]"
    return t


def render(template_name, out_name, n, t):
    text = (REPORT_DIR / template_name).read_text()

    def sub(match):
        kind, key = match.group(1), match.group(2)
        if kind == "num":
            return n[key]
        if kind == "table":
            return t[key]
        if kind == "file":
            return (ROOT / key).read_text()
        raise KeyError(match.group(0))

    text = re.sub(r"\{\{(num|table|file):([^}]+)\}\}", sub, text)
    (REPORT_DIR / out_name).write_text(text)
    todos = re.findall(r"\[\[TODO-HUMAN:[^\]]*\]\]", text)
    print(f"wrote report/{out_name} ({len(text):,} chars, {len(todos)} TODO-HUMAN markers)")


def main():
    n, t = numbers(), tables()
    render("report_template.md", "report.md", n, t)
    render("slides_template.md", "slides.md", n, t)


if __name__ == "__main__":
    main()
