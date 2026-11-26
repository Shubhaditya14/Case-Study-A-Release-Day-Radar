# Team contribution split — Team Sata and Dory Letting

The team agreed an **equal split**. Each member owns one part of the project, presents that part in the talk
(`report/speaker_script.md`) and answers viva questions on it. Every piece of work is listed under exactly one
member. Code was written with the help of generative AI, as disclosed in Appendix I of the report.

| Member                | USN        | Role                                         | Slides | Contribution |
| :-------------------- | :--------- | :------------------------------------------- | :----: | -----------: |
| Punyashloka Mahapatra | 1RV23EC110 | Project lead and framing                     |  1–2   |          20% |
| Shubhaditya Bechan    | 1RV23AI099 | Data sources and big-data pipeline           |  3–4   |          20% |
| Manan Joshi           | 1RV23CD029 | Cleaning, matching and database              |  5–6   |          20% |
| Tanikonda Sai Karan   | 1RV23IS129 | Sentiment, analysis and charts               |  7–8   |          20% |
| Wangchen T            | 1RV23CY060 | Recommendation, limitations and presentation |  9–10  |          20% |
| **Total**             |            |                                              |        |     **100%** |

---

## Punyashloka Mahapatra — project lead and framing

- **Question and decision:** framed the question around the Head of Distribution's add / cut / promote call
  (report sections a and b).
- **Film selection:** `src/00_verify_films.py` checked 18 candidates. The 10 approved films (M6) are in
  `data/manual/film_list.csv`, and the drop reasons are in `film_list_proposed.csv`.
- **Checking the sources work:** `src/00_smoke_test.py` and the Phase 1 check-in `report/phase1_checkin.md`.
- **Setup:** YouTube Data API key (M1), TMDb key (M2), MySQL 8 in Docker on port 3307 (M3).
- **Repository and reproducibility:** GitHub repository, `Makefile` (`make all`), `README.md` and the report
  builder `src/14_build_report.py`.

## Shubhaditya Bechan — data sources and big-data pipeline

- **Collection from the APIs:** `src/01_collect_wikipedia.py` (MediaWiki API), `src/02_collect_tmdb.py` and
  `src/03_collect_youtube.py` (18 trailer versions, 354,592 comments, resumable).
- **YouTube quota guard:** `src/utils.py`, a hard cap of 10,000 units a day, reserved before every call.
- **Flattening JSON into tables:** `src/04_flatten_json.py` (`pd.json_normalize`; usernames dropped here).
- **Other sources:** Google Trends exports for 10 films (M7) and the Frankfurter/ECB exchange rate.
- **PySpark job:** `src/08_spark_text_job.py` and `notebooks/spark_text_job.ipynb`, 400,008 texts →
  14.3 million words → top terms by film, with row counts after every stage.
- **Source register and V profile:** `src/12_documentation_tables.py`, report section c.

## Manan Joshi — cleaning, matching and database

- **Film-name matching:** `src/05_match_films.py`, rapidfuzz on 56 title strings (≥ 95 accept, 70–94 human
  check in M9, < 70 reject). It rejected the 2025 "Dhurandhar".
- **Type casting and missing values:** `src/06_clean_typecast.py`, ₹ ranges → midpoint, lakh and Indian digit
  grouping, USD → ₹ at the ECB rate, UTC → IST, text counts → integers, Trends "<1" → 0.5.
- **Trailer start-time fix:** `trailer_start_times()` in `src/utils.py`. Raid 2 had comments 20.7 hours
  before its official publish time.
- **Cleaning log:** `outputs/cleaning_log.csv` (32 decisions), report section e and Appendix E.
- **Database:** `sql/schema.sql` (5 tables, primary and foreign keys), `src/09_load_mysql.py`, the ER diagram
  and the 7 queries in `sql/queries.sql` (Appendix A).

## Tanikonda Sai Karan — sentiment, analysis and charts

- **Sentiment:** `src/07_sentiment.py`. VADER was validated on IMDb 50K first (accuracy 0.70, macro-F1 0.69),
  then applied to the comments, with its blind spots measured.
- **Analysis:** `src/10_analysis.py`, z-scores, Spearman correlations (including a partial correlation for
  sentiment), the leave-one-out Buzz Index, and the bot-burst and pre-publish copy-paste checks.
- **Charts:** `src/11_charts.py`, six charts with finding-style titles.
- **Spreadsheet vs pandas (M10):** the Google Sheets step, `src/13_compare_spreadsheet.py`, Appendix D.
- **Findings:** report section f.

## Wangchen T — recommendation, limitations and presentation

- **Recommendation for next Friday:** report section g.
- **Limitations, bias and reflection:** report sections h and i.
- **Presentation:** `report/slides.pptx` (10 slides with speaker notes, built from `report/slides_template.md`)
  and `report/speaker_script.md`.
- **AI-use disclosure:** `report/appendix_ai_use.md`.
