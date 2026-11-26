"""
Step 11 — Charts for the report and slides. Every title states the finding, with the real numbers
filled in from outputs/tables (nothing typed by hand), and every chart says its n.

Colour rules (from our chart style guide):
  - Hindi = blue, Regional = orange, always the same, on every chart (colour follows the group)
  - context/background lines are grey; text is never coloured
  - one y-axis per chart (no dual axes), thin marks, light solid gridlines
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")  # draw to files, no window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import DATA_CLEAN, OUT_CHARTS, OUT_TABLES  # noqa: E402

BLUE, ORANGE = "#2a78d6", "#eb6834"          # categorical slots 1 and 2
GREY, GREY_LIGHT = "#8a8985", "#d8d7d2"
INK, INK_2 = "#0b0b0b", "#52514e"
SURFACE = "#fcfcfb"
GROUP_COLOR = {False: BLUE, True: ORANGE}     # key = is_regional

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
    "axes.edgecolor": GREY_LIGHT, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
    "axes.grid": True, "grid.color": "#ecebe7", "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
})

SHORT = {"chhaava": "Chhaava", "saiyaara": "Saiyaara", "sitaare_zameen_par": "Sitaare Zameen Par",
         "housefull_5": "Housefull 5", "raid_2": "Raid 2", "dhurandhar_the_revenge": "Dhurandhar: The Revenge",
         "kantara_chapter_1": "Kantara: Ch. 1", "lokah_chapter_1": "Lokah Ch. 1", "l2_empuraan": "L2: Empuraan",
         "peddi": "Peddi"}


def legend_groups(ax, loc="upper left"):
    for regional, label in [(False, "Hindi"), (True, "Regional (Kannada, Malayalam, Telugu)")]:
        ax.scatter([], [], s=50, color=GROUP_COLOR[regional], label=label)
    ax.legend(loc=loc, frameon=False, fontsize=9)


def footnote(fig, text):
    # Placed BELOW the axes (negative y); bbox_inches="tight" grows the image to fit it
    fig.text(0.01, -0.02, text, fontsize=8, color=INK_2, ha="left", va="top", wrap=True)


def save(fig, name):
    fig.savefig(OUT_CHARTS / name, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"saved outputs/charts/{name}")


def rho_of(corr, feature, subset="all films"):
    row = corr[(corr.feature == feature) & (corr.subset == subset)].iloc[0]
    return row.spearman_rho, row.p_value, int(row.n)


def chart_views_vs_weekend(f, corr):
    """Two sources combined: YouTube trailer views × Wikipedia first-weekend collections."""
    rho, p, n = rho_of(corr, "total_views")
    rho8, _, n8 = rho_of(corr, "total_views", "excluding flagged weekend figures")
    fig, ax = plt.subplots(figsize=(8, 5))
    for row in f.itertuples():
        ax.scatter(row.total_views / 1e6, row.first_weekend_per_day, s=70, color=GROUP_COLOR[row.is_regional],
                   edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.annotate(SHORT[row.film_id], (row.total_views / 1e6, row.first_weekend_per_day), xytext=(6, 4),
                    textcoords="offset points", fontsize=8.5, color=INK_2)
    ax.set_xscale("log")
    ax.set_xticks([15, 30, 60, 120]); ax.set_xticklabels(["15M", "30M", "60M", "120M"])
    ax.minorticks_off()   # hide log-scale minor labels like "2×10¹"
    ax.set_xlabel("Trailer views, all official language versions (YouTube, log scale)")
    ax.set_ylabel("First-weekend collection per day (₹ crore)")
    ax.set_title(f"More-watched trailers went with bigger first weekends — loosely (ρ = {rho:.2f}, n = {n})")
    legend_groups(ax)
    footnote(fig, f"Spearman ρ = {rho:.2f} (p = {p:.2f}); without the 2 flagged weekend figures ρ = {rho8:.2f}, n = {n8}. "
                  "Views are today's totals, so they include post-release viewing. Correlation, not cause.")
    save(fig, "01_views_vs_first_weekend.png")


def chart_normalised_gap(f):
    """Normalised: z-score of log views vs z-score of first-weekend per day, one row per film."""
    d = f.assign(gap=f.z_outcome - f.z_log_views).sort_values("gap")
    over = d.iloc[0]; under = d.iloc[-1]
    fig, ax = plt.subplots(figsize=(8, 5.2))
    y = np.arange(len(d))
    for i, row in enumerate(d.itertuples()):
        ax.plot([row.z_log_views, row.z_outcome], [i, i], color=GREY_LIGHT, linewidth=2, zorder=1)
        ax.scatter(row.z_log_views, i, s=55, facecolor=SURFACE, edgecolor=GROUP_COLOR[row.is_regional], linewidth=2, zorder=3)
        ax.scatter(row.z_outcome, i, s=55, color=GROUP_COLOR[row.is_regional], edgecolor=SURFACE, linewidth=1.5, zorder=3)
    ax.set_yticks(y); ax.set_yticklabels([SHORT[i] for i in d.film_id])
    ax.axvline(0, color=GREY, linewidth=1)
    ax.set_xlabel("z-score (0 = average of the 10 films; ±1 = one standard deviation)")
    ax.set_title(f"On one scale, {SHORT[over.film_id]} had far more buzz than box office;\n"
                 f"{SHORT[under.film_id]} out-earned even its large buzz (n = {len(d)})")
    ax.scatter([], [], s=55, facecolor=SURFACE, edgecolor=INK_2, linewidth=2, label="Trailer views (z of log10)")
    ax.scatter([], [], s=55, color=INK_2, label="First weekend per day (z)")
    ax.scatter([], [], s=50, color=BLUE, label="Hindi"); ax.scatter([], [], s=50, color=ORANGE, label="Regional")
    ax.legend(loc="lower right", frameon=False, fontsize=8.5)
    footnote(fig, "Hollow = trailer views, filled = first weekend. Sorted by (box-office z − views z): top rows earned MORE than their buzz suggested, bottom rows LESS.")
    save(fig, "02_normalised_buzz_vs_box_office.png")


def chart_sentiment(f, corr):
    rho, p, n = rho_of(corr, "sentiment_7d")
    partial = corr[corr.feature.str.contains("partial")].iloc[0].spearman_rho
    fig, ax = plt.subplots(figsize=(8, 5))
    for row in f.itertuples():
        ax.scatter(row.sentiment_7d, row.first_weekend_per_day, s=70, color=GROUP_COLOR[row.is_regional],
                   edgecolor=SURFACE, linewidth=2, zorder=3)
        nudge = {"housefull_5": (6, -12), "sitaare_zameen_par": (6, 6)}.get(row.film_id, (6, 4))
        ax.annotate(SHORT[row.film_id], (row.sentiment_7d, row.first_weekend_per_day), xytext=nudge,
                    textcoords="offset points", fontsize=8.5, color=INK_2)
    ax.set_xlabel("Mean VADER sentiment of first-week trailer comments (−1 negative … +1 positive)")
    ax.set_ylabel("First-weekend collection per day (₹ crore)")
    ax.set_title(f"Happier trailer comments did not mean bigger openings (ρ = {rho:.2f}, n = {n})")
    legend_groups(ax, loc="center left")
    footnote(fig, f"Spearman ρ = {rho:.2f} (p = {p:.2f}); after controlling for views, partial ρ = {partial:.2f}. "
                  "Comments VADER cannot read (score 0: Indian scripts, Hinglish) excluded.")
    save(fig, "03_sentiment_vs_first_weekend.png")


def chart_velocity(vel):
    """Comment velocity: share of each film's first-72h comments per hour, small multiples."""
    comments = pd.read_csv(DATA_CLEAN / "comments.csv", usecols=["film_id", "published_ts"], parse_dates=["published_ts"])
    trailers = pd.read_csv(DATA_CLEAN / "trailers.csv", parse_dates=["publish_ts"])
    main = trailers[trailers.is_main_trailer].set_index("film_id")["publish_ts"]
    films = pd.read_csv(DATA_CLEAN / "films.csv").set_index("film_id")
    comments["h"] = ((comments.published_ts - comments.film_id.map(main)).dt.total_seconds() // 3600)
    first = comments[(comments.h >= 0) & (comments.h < 72)]
    median_share = vel.share_in_first_72h.median()

    order = vel.sort_values("comments_per_hour_72h", ascending=False).film_id
    fig, axes = plt.subplots(2, 5, figsize=(12, 5), sharex=True, sharey=True)
    for ax, film_id in zip(axes.flat, order):
        per_hour = first[first.film_id == film_id].groupby("h").size().reindex(range(72), fill_value=0)
        color = ORANGE if films.loc[film_id, "language"] != "Hindi" else BLUE
        ax.plot(per_hour.index, per_hour.values, color=color, linewidth=1.6)
        ax.set_yscale("log"); ax.set_ylim(0.8, 20000)
        ax.set_title(SHORT[film_id], fontsize=9.5, fontweight="bold")
        ax.set_xticks([0, 24, 48, 72])
    for ax in axes[1]:
        ax.set_xlabel("hours after trailer")
    axes[0, 0].set_ylabel("comments per hour (log)"); axes[1, 0].set_ylabel("comments per hour (log)")
    fig.suptitle(f"Trailer buzz is front-loaded: the busiest hour is the first one, and a median {median_share:.0%} of all "
                 f"comments ever posted arrive within 72 h (n = 10 trailers)", x=0.01, ha="left", fontsize=12, fontweight="bold")
    footnote(fig, "Top-level comments on each film's main trailer, timestamps converted to IST. Blue = Hindi, orange = regional. "
                  "Panels sorted by comments/hour.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    save(fig, "04_comment_velocity_first_72h.png")


def chart_trends(vel):
    trends = pd.read_csv(DATA_CLEAN / "trends_daily.csv", parse_dates=["date"])
    films = pd.read_csv(DATA_CLEAN / "films.csv", parse_dates=["release_date"]).set_index("film_id")
    trends["day"] = (trends.date - trends.film_id.map(films.release_date)).dt.days
    window = trends[(trends.day >= -14) & (trends.day <= 14)]
    median = window.groupby("day").interest.median()
    half = vel.trends_days_peak_to_half.median()
    fig, ax = plt.subplots(figsize=(8, 4.6))
    for film_id, g in window.groupby("film_id"):
        ax.plot(g.day, g.interest, color=GREY_LIGHT, linewidth=1.2)
    ax.plot(median.index, median.values, color=BLUE, linewidth=2.4, label="Median of 10 films")
    ax.axvline(0, color=GREY, linewidth=1)
    ax.text(-0.4, 92, "release day", fontsize=8.5, color=INK_2, ha="right")
    ax.set_xlabel("days from release"); ax.set_ylabel("Search interest, India (peak = 100)")
    ax.set_title(f"Search interest peaks on release day and halves within about {half:.0f} days (n = 10)")
    ax.plot([], [], color=GREY_LIGHT, linewidth=1.2, label="One film")
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    footnote(fig, "Google Trends exports are scaled 0–100 separately per film, so only the shape is comparable across films.")
    save(fig, "05_trends_rise_and_decay.png")


def chart_buzz_loo(loo, f):
    hits = int(loo.call_correct.sum())
    misses = [SHORT[x] for x in loo[~loo.call_correct].held_out_film]
    d = loo.merge(f[["film_id", "is_regional"]], left_on="held_out_film", right_on="film_id")
    fig, ax = plt.subplots(figsize=(7, 5.4))
    ax.plot([1, 10], [1, 10], color=GREY_LIGHT, linewidth=1.5, zorder=1)
    ax.text(7.4, 6.55, "perfect prediction", fontsize=8, color=INK_2, ha="right")
    for row in d.itertuples():
        ax.scatter(row.predicted_rank_of_10, row.actual_rank_of_10, s=75, color=GROUP_COLOR[row.is_regional],
                   edgecolor=SURFACE, linewidth=2, zorder=3, marker="o" if row.call_correct else "X")
        ax.annotate(SHORT[row.held_out_film], (row.predicted_rank_of_10, row.actual_rank_of_10), xytext=(6, -3),
                    textcoords="offset points", fontsize=8.5, color=INK_2)
    ax.set_xlim(0.5, 11.5); ax.set_ylim(10.5, 0.5)
    ax.set_xticks(range(1, 11)); ax.set_yticks(range(1, 11))
    ax.set_xlabel("Buzz Index rank (1 = most buzz), each film scored by an index fitted WITHOUT it")
    ax.set_ylabel("Actual first-weekend rank (1 = biggest)")
    ax.set_title(f"A Buzz Index fitted on the other 9 films called {hits} of 10 openings\nabove/below median — it missed {' and '.join(misses)}")
    ax.scatter([], [], color=INK_2, marker="o", label="call right"); ax.scatter([], [], color=INK_2, marker="X", label="call wrong")
    ax.scatter([], [], color=BLUE, label="Hindi"); ax.scatter([], [], color=ORANGE, label="Regional")
    ax.legend(loc="upper right", frameon=False, fontsize=8.5)
    footnote(fig, f"Leave-one-out test, mean rank error {loo.rank_error.mean():.1f} places. A coin toss would get ~5 of 10 right. n = 10 is very small.")
    save(fig, "06_buzz_index_leave_one_out.png")


def main():
    OUT_CHARTS.mkdir(parents=True, exist_ok=True)
    f = pd.read_csv(OUT_TABLES / "film_features.csv")
    corr = pd.read_csv(OUT_TABLES / "correlations.csv")
    vel = pd.read_csv(OUT_TABLES / "velocity_by_film.csv")
    loo = pd.read_csv(OUT_TABLES / "buzz_index_loo.csv")
    chart_views_vs_weekend(f, corr)
    chart_normalised_gap(f)
    chart_sentiment(f, corr)
    chart_velocity(vel)
    chart_trends(vel)
    chart_buzz_loo(loo, f)


if __name__ == "__main__":
    main()
