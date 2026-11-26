# Release Day Radar — Case Study A

*Data and Storytelling · Module 1: Understanding Data — Types, Sources and Preparation*

**Repo:** https://github.com/Shubhaditya14/Case-Study-A-Release-Day-Radar

**Question:** Did trailer-week YouTube engagement predict first-weekend collections for 10 Hindi and regional films released in 2025–26, and does audience sentiment add anything beyond raw views?

**Answer, in brief:**
- Trailer reach is a **loose** hint: Spearman ρ = 0.65, n = 10.
- Comment sentiment adds **nothing**.
- Comment counts can be **gamed**: Raid 2's pre-publish comments are 89% copy-paste.
- Make the screens call on Friday's collections. The full write-up is in `report/report.pdf`.

---

## 1. What you need

| Tool | Version we used | Why |
|---|---|---|
| macOS or Linux | macOS 27 | `make`, shell |
| [uv](https://docs.astral.sh/uv/) | any | creates the Python 3.12 virtual environment |
| Java | 17+ (we used 21) | PySpark runs on the JVM |
| Docker Desktop **or** MySQL 8 | MySQL 8.0.46 in Docker | relational model + SQL queries |
| Graphviz (`dot`) | any | ER and pipeline diagrams |
| pandoc | 3.x | report → .docx/.html, slides → .pptx |
| Google Chrome | any | prints report.html → report.pdf |

## 2. Set up (once)

```bash
git clone https://github.com/Shubhaditya14/Case-Study-A-Release-Day-Radar.git
cd Case-Study-A-Release-Day-Radar
make setup                    # .venv with Python 3.12 + requirements.txt
cp .env.example .env          # then fill in the values below
```

| `.env` variable | How to get it |
|---|---|
| `YT_API_KEY` | Google Cloud Console → new project → enable **YouTube Data API v3** → Credentials → API key (MANUAL_STEPS.md M1) |
| `TMDB_API_KEY` | themoviedb.org → Settings → API → request a developer key; use the short "API Key" (M2) |
| `MYSQL_*` | `docker run -d --name radar-mysql -p 3307:3306 -e MYSQL_ROOT_PASSWORD=<pw> -e MYSQL_DATABASE=release_day_radar -e MYSQL_USER=radar -e MYSQL_PASSWORD=<pw> mysql:8.0`, then `MYSQL_PORT=3307` (M3) |
| `YT_DAILY_BUDGET` | optional; can only **lower** the 10,000-unit daily cap |

**Files you add by hand** (they can't be downloaded by script):

- `data/manual/imdb_50k.csv`: the IMDb 50K labelled reviews from Homework 1.2 ([Kaggle copy](https://www.kaggle.com/datasets/lakshmi25npathi/imdb-dataset-of-50k-movie-reviews)), renamed to this name.
- `data/manual/trends_<film_id>.csv`: one Google Trends export per film. Ready-made links with the exact region, dates and term are in MANUAL_STEPS.md M7. These 10 files are already committed.

Check that every source answers: `make smoke`

## 3. Run everything

```bash
docker start radar-mysql      # if it isn't running
make all                      # collect → clean → spark → sql → charts → report
```

| Target | Scripts | Notes |
|---|---|---|
| `make collect` | `01`–`04` | Wikipedia, TMDb, YouTube, then flatten with `json_normalize`. **Needs about 4,500 YouTube quota units** (all comments on 10 trailers). The comment download resumes where it stopped if the daily cap is hit. Raw files are cached, so reruns cost 0 units. |
| `make clean` | `05`–`07` | Match titles, type-cast, VADER (about 3 min) |
| `make spark` | `08` | PySpark local mode, 400k texts (about 2 min) |
| `make sql` | `09` | Rebuilds the schema, loads 5 tables, runs `sql/queries.sql` |
| `make charts` | `10`–`12` | Analysis, 6 charts, source register / inventory / V profile |
| `make report` | `13`–`14` + pandoc | Fills the report/slides templates with pipeline numbers → `.docx`, `.pdf`, `.pptx` |
| `make zip` | — | `TeamName_FinalSubmission.zip` |

Raw data in `data/raw/` is **gitignored**: it holds commenter usernames, and it is 370 MB. `make collect` rebuilds it from the APIs. The full cleaned comment table (45 MB) is also gitignored. A hashed 2,000-row sample is committed as `data/clean/comments_sample.csv`.

## 4. Outputs

| Path | What |
|---|---|
| `report/report.pdf`, `report.docx` | The report (10-page body + appendices), generated from `report/report_template.md` |
| `report/slides.pptx` | 10 slides with speaker notes |
| `outputs/charts/` | 6 charts, each titled with its finding |
| `outputs/cleaning_log.csv` | Every cleaning decision, with real row counts (each script appends its own) |
| `outputs/tables/` | Source register, data inventory, V profile, SQL results, Spark counts, correlations, Buzz Index test, bot checks |
| `data/clean/` | Final tables: films, trailers, box_office, trends_daily, comments sample, film_matches |
| `notebooks/` | `spark_text_job.ipynb` (executed, outputs saved), `exploration.ipynb` |
| `report/er_diagram.png`, `report/pipeline.png` | Generated from `.dot` sources |

## 5. Repository map

```
src/00_smoke_test.py         every source returns data for one film
src/00_verify_films.py       Phase 1: which of 18 candidate films are usable
src/01–04                    collect + flatten          src/05  fuzzy title matching
src/06                       cleaning & type casting    src/07  VADER (validated on IMDb first)
src/08                       PySpark text job           src/09  MySQL load + queries
src/10                       analysis + Buzz Index      src/11  charts
src/12                       register / inventory / V profile
src/13                       Sheets-vs-pandas check     src/14  build report from templates
src/utils.py                 paths, cleaning log, polite HTTP, YouTube quota guard
sql/schema.sql, sql/queries.sql
MANUAL_STEPS.md              the human steps (keys, approvals, Google Sheets)
QA_PREP.md                   plain-English explanation of every script + viva questions
```

## 6. Ground rules we followed

- **Official APIs only.** No IMDb or Sacnilk scraping, nothing behind a login. The MediaWiki API is called with a descriptive User-Agent and a 1-second pause between calls.
- **YouTube quota hard-capped** at 10,000 units per Pacific day, in `src/utils.py`.
- **Privacy.** Author names, channel IDs and profile URLs are dropped in step 04 and never leave `data/raw/`.
- **No invented numbers.** Every first-weekend figure is checked word for word against the downloaded Wikipedia page, and every number in the report is filled from pipeline outputs.
