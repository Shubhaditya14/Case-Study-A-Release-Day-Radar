# Manual steps — living checklist

Claude does every AUTO step. These are the steps only a human can do (accounts, keys, approvals, clicks in Google Sheets).
Reply `done` in the Claude session after each one; Claude runs the check and ticks it here.

## Phase 1 — Frame

- [x] **M1 — Get a YouTube Data API v3 key** (verified 2026-11-26: smoke test PASS)
  - WHY: rubric "Data sourcing and variety" — YouTube is our JSON API for trailer stats and our unstructured comment text.
  - DO THIS:
    1. Go to https://console.cloud.google.com/ and sign in with a Google account.
    2. Top bar → project dropdown → **New Project** → name it `release-day-radar` → **Create**. Make sure it is selected.
    3. Left menu → **APIs & Services → Library** → search `YouTube Data API v3` → open it → **Enable**.
    4. Left menu → **APIs & Services → Credentials** → **+ Create credentials → API key**. Copy the key.
    5. (Recommended) Click the key → **API restrictions → Restrict key** → tick only *YouTube Data API v3* → **Save**.
    6. In the repo root run `cp .env.example .env` (only the first time), open `.env`, paste the key after `YT_API_KEY=` (no quotes, no spaces).
  - PUT RESULT HERE: `.env` → `YT_API_KEY`
  - HOW I'LL CHECK: `.venv/bin/python src/00_smoke_test.py` must print `PASS  YouTube Data API v3` (costs 1 quota unit).
  - TIME: ~5 min

- [x] **M2 — Get a TMDb API key** (verified 2026-11-26: smoke test PASS, Chhaava tmdb_id 1196943)
  - WHY: rubric "Data sourcing and variety" — second JSON API (genre, runtime, language, cast).
  - DO THIS:
    1. Create a free account at https://www.themoviedb.org/signup and verify your email.
    2. Avatar (top right) → **Settings** → **API** (left menu) → **Create** / **Request an API key** → choose **Developer**.
    3. Accept the terms. Fill the form: type *Education*, app name `Release Day Radar`, URL = our GitHub repo URL, summary "University course project analysing film buzz".
    4. Copy the **API Key** (the short 32-character one — *not* the long "API Read Access Token").
    5. Paste it into `.env` after `TMDB_API_KEY=`.
  - PUT RESULT HERE: `.env` → `TMDB_API_KEY`
  - HOW I'LL CHECK: `src/00_smoke_test.py` must print `PASS  TMDb API` with Chhaava as the top result.
  - TIME: ~5 min

- [x] **M3 — Install MySQL 8 and create the database + user** (verified 2026-11-26: Docker container `radar-mysql`, MySQL 8.0.46 on host port 3307 — 3306 was taken by a pre-existing local MySQL)
  - WHY: rubric "Representation and SQL" — relational schema with keys, 5+ queries.
  - DO THIS — pick ONE option:
    - **Option A: Docker (easiest, nothing installed on your Mac)**
      1. Open Docker Desktop and wait until it says "running".
      2. Pick a password, then run (replace `CHOOSE_A_PASSWORD` both times):
         ```bash
         docker run -d --name radar-mysql -p 3307:3306 -e MYSQL_ROOT_PASSWORD=CHOOSE_A_PASSWORD -e MYSQL_DATABASE=release_day_radar -e MYSQL_USER=radar -e MYSQL_PASSWORD=CHOOSE_A_PASSWORD mysql:8.0
         ```
      3. Wait ~30 s, then check: `docker exec radar-mysql mysql -uradar -pCHOOSE_A_PASSWORD -e "SELECT VERSION();"` should print `8.0.x`.
      4. Later sessions: `docker start radar-mysql`.
    - **Option B: Homebrew (native install)**
      1. `brew install mysql@8.4` then `brew services start mysql@8.4`
      2. `$(brew --prefix mysql@8.4)/bin/mysql -uroot` and paste:
         ```sql
         CREATE DATABASE release_day_radar CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
         CREATE USER 'radar'@'localhost' IDENTIFIED BY 'CHOOSE_A_PASSWORD';
         GRANT ALL PRIVILEGES ON release_day_radar.* TO 'radar'@'localhost';
         FLUSH PRIVILEGES;
         ```
  - Then fill in `.env`: `MYSQL_HOST=127.0.0.1`, `MYSQL_PORT=3307` (Docker) or `3306` (Homebrew), `MYSQL_USER=radar`, `MYSQL_PASSWORD=<your password>`, `MYSQL_DB=release_day_radar`.
  - PUT RESULT HERE: `.env` → `MYSQL_*`
  - HOW I'LL CHECK: a Python/SQLAlchemy connection that runs `SELECT VERSION()` and prints 8.x.
  - TIME: ~10 min

- [x] **M4 — Copy the IMDb 50K labelled reviews from Homework 1.2** (verified 2026-11-26: 50,000 rows, 25,000 pos / 25,000 neg, 0 nulls, 418 duplicate texts → handled in Phase 3)
  - WHY: rubric "Analysis, PySpark" — validates VADER (accuracy/F1) and lifts the Spark job past 50,000 rows.
  - DO THIS:
    1. Find the CSV from Homework 1.2 (usually `IMDB Dataset.csv`, 50,000 rows, columns `review`, `sentiment`).
    2. Copy it to `data/manual/imdb_50k.csv` (exact name). It is gitignored because it is ~65 MB.
    3. If you no longer have it: download from https://www.kaggle.com/datasets/lakshmi25npathi/imdb-dataset-of-50k-movie-reviews and rename.
  - PUT RESULT HERE: `data/manual/imdb_50k.csv`
  - HOW I'LL CHECK: pandas loads it, 50,000 rows, columns `review` + `sentiment`, labels only `positive`/`negative`.
  - TIME: ~3 min

- [x] **M5 — GitHub repo: add teammates and push** (push verified 2026-11-26; adding teammates still deferred)
  - WHY: rubric "Analysis, PySpark and reproducibility" — repo with commits from every member.
  - DO THIS:
    1. The repo already exists: https://github.com/Shubhaditya14/Case-Study-A-Release-Day-Radar
    2. In this folder run `git push origin main`.
    3. *(Deferred by user on 2026-11-26)* Add teammates as collaborators (**Settings → Collaborators → Add people**) and list them in `report/team.md`. Needed before M8 and the final submission (rubric wants commits from every member).
  - PUT RESULT HERE: pushed `main`
  - HOW I'LL CHECK: `git status -sb` shows nothing ahead of origin.
  - TIME: ~5 min

- [x] **M6 — Approve the film list** (approved 2026-11-26: 10 recommended films; outcome = first-weekend worldwide gross ÷ weekend days; trailers summed across official language versions) → `data/manual/film_list.csv`

## Phase 2 — Collect and model

- [x] **M7 — Export Google Trends CSVs (one per film)** (verified 2026-11-26: 10 files, full daily coverage, 0 missing days; 4 "<1" values in Chhaava to type-cast)
  - WHY: rubric "Data sourcing and variety" — Trends is our CSV source and our Velocity evidence (rise and decay of interest).
  - DO THIS (repeat for each of the 10 rows below):
    1. Click the film's **open** link. It already sets Region = **India**, the date range, and the search term.
       Check the top bar shows: India · the right dates · All categories · Web Search. If Google suggests a "Topic" (e.g. "Chhaava — 2025 film"), **stay on the plain search term** so every film is measured the same way.
    2. Make sure the chart is daily (it is, because each range is under 9 months).
    3. On the **Interest over time** box, click the **download ↓** icon (top right of the box). It saves `multiTimeline.csv`.
    4. Rename it to the file name in the last column and move it into `data/manual/`.
    5. If Trends shows "Hmm, your search doesn't have enough data", tell me the film — don't make up a file.
  - Notes: one film per export (don't compare two terms in one chart). Trends scales each export 0–100 on its own, so we only use the *shape* (rise and decay), not the size, across films. "Saiyaara" is also a popular song name and "Peddi"/"Lokah" are common words — I'll flag that as a limitation.

    | film_id | search term | dates | link | save as |
    |---|---|---|---|---|
    | `chhaava` | Chhaava | 2025-01-15 → 2025-02-28 | [open](https://trends.google.com/trends/explore?date=2025-01-15%202025-02-28&geo=IN&q=Chhaava) | `data/manual/trends_chhaava.csv` |
    | `saiyaara` | Saiyaara | 2025-07-01 → 2025-08-01 | [open](https://trends.google.com/trends/explore?date=2025-07-01%202025-08-01&geo=IN&q=Saiyaara) | `data/manual/trends_saiyaara.csv` |
    | `sitaare_zameen_par` | Sitaare Zameen Par | 2025-05-06 → 2025-07-04 | [open](https://trends.google.com/trends/explore?date=2025-05-06%202025-07-04&geo=IN&q=Sitaare%20Zameen%20Par) | `data/manual/trends_sitaare_zameen_par.csv` |
    | `housefull_5` | Housefull 5 | 2025-05-20 → 2025-06-20 | [open](https://trends.google.com/trends/explore?date=2025-05-20%202025-06-20&geo=IN&q=Housefull%205) | `data/manual/trends_housefull_5.csv` |
    | `raid_2` | Raid 2 | 2025-04-01 → 2025-05-15 | [open](https://trends.google.com/trends/explore?date=2025-04-01%202025-05-15&geo=IN&q=Raid%202) | `data/manual/trends_raid_2.csv` |
    | `dhurandhar_the_revenge` | Dhurandhar 2 | 2026-02-28 → 2026-04-02 | [open](https://trends.google.com/trends/explore?date=2026-02-28%202026-04-02&geo=IN&q=Dhurandhar%202) | `data/manual/trends_dhurandhar_the_revenge.csv` |
    | `kantara_chapter_1` | Kantara Chapter 1 | 2025-09-15 → 2025-10-16 | [open](https://trends.google.com/trends/explore?date=2025-09-15%202025-10-16&geo=IN&q=Kantara%20Chapter%201) | `data/manual/trends_kantara_chapter_1.csv` |
    | `lokah_chapter_1` | Lokah | 2025-08-17 → 2025-09-11 | [open](https://trends.google.com/trends/explore?date=2025-08-17%202025-09-11&geo=IN&q=Lokah) | `data/manual/trends_lokah_chapter_1.csv` |
    | `l2_empuraan` | Empuraan | 2025-03-12 → 2025-04-10 | [open](https://trends.google.com/trends/explore?date=2025-03-12%202025-04-10&geo=IN&q=Empuraan) | `data/manual/trends_l2_empuraan.csv` |
    | `peddi` | Peddi | 2026-05-11 → 2026-06-18 | [open](https://trends.google.com/trends/explore?date=2026-05-11%202026-06-18&geo=IN&q=Peddi) | `data/manual/trends_peddi.csv` |

  - PUT RESULT HERE: `data/manual/trends_<film_id>.csv` (10 files)
  - HOW I'LL CHECK: all 10 files exist, each parses to one row per day covering its full date range, interest values 0–100.
  - TIME: ~15 min
- [ ] **M8 — Each teammate makes one meaningful commit** — *deferred by user*; needs the collaborator part of M5 first.

## Phase 3 — Clean and analyse

- [x] **M9 — Confirm uncertain film-name matches (score 70–94)** (confirmed 2026-11-26: both yes → data/manual/match_confirmations.csv; re-run shows 2 applied, 0 pending)
  - WHY: rubric "Cleaning and preprocessing" — film-name matching must be justified; a wrong join corrupts every number after it.
  - DO THIS:
    1. Open `data/manual/match_review.csv` (2 rows). For each row, read `source_title` and `best_film_id`.
    2. If it is the same film, type `yes` in the `confirmed` column; if not, type `no`.
    3. Save the file as `data/manual/match_confirmations.csv` (same columns).
  - PUT RESULT HERE: `data/manual/match_confirmations.csv`
  - HOW I'LL CHECK: re-run `src/05_match_films.py`; it must report "human confirmations applied: 2" and 0 rows left as needs_review.
  - TIME: ~2 min
- [ ] **M10 — Do the ₹-crore cleaning step in Google Sheets + screenshots**
  - WHY: rubric "Cleaning and preprocessing" + brief §4 "Spreadsheets and dataframes": one cleaning step in a spreadsheet, the same in pandas, compared.
  - DO THIS (start a timer — we report how long it took):
    1. Go to https://sheets.new → **File → Import → Upload** → `data/manual/spreadsheet_step_input.csv` → *Replace current sheet* → **Import data**. You get columns A `id`, B `label`, C `raw_text` (36 rows).
    2. Type these headers in row 1: D1 `clean`, E1 `first_num`, F1 `second_num`, G1 `sheet_crore`.
    3. Paste into **D2**:  `=REGEXREPLACE(REGEXREPLACE(REGEXREPLACE(C2,"\[[^\]]*\]",""),"\(US\$[^)]*\)",""),"est\. ","")`
       (removes footnotes like [b], Wikipedia's "(US$17 million)" and "est.")
    4. Paste into **E2**:  `=VALUE(SUBSTITUTE(REGEXEXTRACT(D2,"\d[\d,]*(?:\.\d+)?"),",",""))`
       (first number, commas removed — works for both 1,852.44 and Indian 1,25,000 grouping)
    5. Paste into **F2**:  `=IFERROR(VALUE(SUBSTITUTE(REGEXEXTRACT(D2,"\d\s*(?:crore)?\s*[–—−-]\s*₹?\s*(\d[\d,]*(?:\.\d+)?)"),",","")),"")`
       (second number if the text is a range like ₹325–335 or ₹30−40; blank otherwise)
    6. Paste into **G2**:  `=IF(F2="",E2,(E2+F2)/2)`  (range → midpoint, in ₹ crore)
    7. Select D2:G2 → copy → select D3:G37 → paste (fills all 36 rows).
    8. **Screenshot 1**: the sheet showing columns C–G with several rows → save as `report/img/sheets_result.png`.
       **Screenshot 2**: click cell F2 so the formula bar shows the formula → save as `report/img/sheets_formula.png`.
    9. **File → Download → Comma-separated values (.csv)** → save as `data/manual/spreadsheet_step_output.csv`.
    10. Stop the timer. Reply with: minutes taken, and anything that went wrong (e.g. a formula error you had to fix).
  - PUT RESULT HERE: `data/manual/spreadsheet_step_output.csv`, `report/img/sheets_result.png`, `report/img/sheets_formula.png`, + your time in the reply
  - HOW I'LL CHECK: `src/13_compare_spreadsheet.py` must report "Agree on 36/36 strings" (a pre-check simulating these exact formulas already agrees 36/36).
  - TIME: ~15 min

## Phase 4 — Story and submit

- [ ] **M11 — Fill in the team contribution split** → edit `report/team_contribution.md` (names, roles, %, totals 100). Also fill the team name in `report/report_template.md` and `report/slides_template.md`, then `make report`.
- [ ] **M12 — Everyone reads `QA_PREP.md`; rehearse the 7-minute talk** with `report/speaker_script.md` (replace Speaker A–D with names). Slides: `report/slides.pptx` (10 slides, notes included).
- [ ] **M13 — Submit** → run `make report zip` and submit `Sata_and_Dory_Telling_FinalSubmission.zip` (team: Sata and Dory Telling).
