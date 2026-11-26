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

- [ ] **M5 — GitHub repo: add teammates and push**
  - WHY: rubric "Analysis, PySpark and reproducibility" — repo with commits from every member.
  - DO THIS:
    1. The repo already exists: https://github.com/Shubhaditya14/Case-Study-A-Release-Day-Radar
    2. In this folder run `git push origin main`.
    3. *(Deferred by user on 2026-11-26)* Add teammates as collaborators (**Settings → Collaborators → Add people**) and list them in `report/team.md`. Needed before M8 and the final submission (rubric wants commits from every member).
  - PUT RESULT HERE: pushed `main`
  - HOW I'LL CHECK: `git status -sb` shows nothing ahead of origin.
  - TIME: ~5 min

- [ ] **M6 — Approve the film list** — Claude will propose 10–12 films (checked on Wikipedia, TMDb, YouTube) in `data/manual/film_list_proposed.csv`. You approve or edit it.

## Phase 2 — Collect and model

- [ ] **M7 — Export Google Trends CSVs** — exact settings per film will be written here when we reach it.
- [ ] **M8 — Each teammate makes one meaningful commit** — *deferred by user*; needs the collaborator part of M5 first.

## Phase 3 — Clean and analyse

- [ ] **M9 — Confirm uncertain film-name matches (score < 95)**
- [ ] **M10 — Do the ₹-crore cleaning step in Google Sheets + screenshots into `report/img/`**

## Phase 4 — Story and submit

- [ ] **M11 — Fill in the team contribution split (template provided)**
- [ ] **M12 — Everyone reads `QA_PREP.md`; rehearse the 7-minute talk with the speaker script**
- [ ] **M13 — Rename the final zip with your team name and submit**
