# Claude Code prompt — Case Study A: Release Day Radar

> **How to use:** Make an empty folder, put the brief PDF in it as `docs/brief_case_A.pdf`, open Claude Code in that folder, and paste everything below the line.

---

You are helping my team build **Case Study A — Release Day Radar** for my _Data and Storytelling_ course (Module 1: Understanding Data — Types, Sources and Preparation). The full brief is in `docs/brief_case_A.pdf`. Read it first, and treat it as the source of truth if anything below disagrees with it.

I have to explain every line in a Q&A, so build this so I can understand it, not just so it runs.

## 0. How you must work with me

1. **Split the work into AUTO and MANUAL steps.** Do every AUTO step yourself. When you reach a MANUAL step, **stop**, print a block exactly like the one below, and wait for me to reply `done` before continuing:

   ```
   ════════ MANUAL STEP M<n>: <title> ════════
   WHY:      <one line: which rubric item this satisfies>
   DO THIS:
     1. <exact click-by-click or command-by-command instruction>
     2. ...
   PUT RESULT HERE: <exact file path / env var name>
   HOW I'LL CHECK:  <the check you'll run when I say done>
   TIME:     ~<minutes>
   ═══════════════════════════════════════════
   ```

2. Keep **`MANUAL_STEPS.md`** at the repo root as a living checklist (`- [ ] M1 …`, `- [x] M1 …`). Number every manual step, include the same instructions as in the STOP block, and tick each one off once you've verified it.
3. **Never fabricate data, numbers or findings.** If a source fails, stop, tell me what failed, and offer a replacement source. Every number in the report must come from a file the pipeline produced.
4. Work in phases (Section 6). At the end of each phase, print a short summary: what was built, row counts, what's next, and which manual steps are pending.
5. Commit after each logical step with clear messages. Tell me when teammates need to make their own commits (see M-steps below).
6. Write beginner-readable code: short functions, a comment above each block explaining _why_, and no clever one-liners.

## 1. The question (default — confirm with me in Phase 1)

> **"Did trailer-week YouTube engagement predict opening-weekend collections for 10–12 Hindi and regional films released in 2025–26 — and does audience sentiment add anything beyond raw views?"**

- **Decision it serves:** the Head of Distribution's Friday call on whether to add screens, cut screens, or spend more on promotion.
- **Scope rule from the brief:** at least 8 films (aim for 10–12, mixing Hindi and at least 3 regional films) released in 2025–26.
- **Candidate films to verify (do not assume they're correct):** Chhaava, Saiyaara, Sitaare Zameen Par, Housefull 5, Raid 2, War 2, Coolie, Kantara: Chapter 1, Thamma, Jolly LLB 3, Dhurandhar, plus 2026 releases. For each one, check on Wikipedia that it released in 2025–26, has an opening-weekend figure, and has an official trailer on YouTube. Propose a final list of 10–12 with a reason for any you drop, then **STOP for me to approve it (manual step)**.

## 2. Data sources (minimum 3 sources, 3 shapes, at least 1 JSON API)

| Shape                   | Source                                                                                                                | Method                                                                                          | Format                             |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | ---------------------------------- |
| Structured              | Wikipedia film pages (box-office infobox and tables: opening weekend, budget, gross, release date, screens if listed) | **MediaWiki API** (`action=parse`), not raw HTML scraping; parse tables with `pandas.read_html` | HTML tables inside a JSON response |
| Structured              | Google Trends daily interest per film (from trailer launch to release + 14 days)                                      | **Manual CSV export** (pytrends is unreliable, so don't use it)                                 | CSV                                |
| Semi-structured         | **YouTube Data API v3**: official trailer video stats (views, likes, comment count, publish date)                     | `videos.list`, `search.list` (only if needed; it costs 100 quota units per call)                | JSON                               |
| Semi-structured         | **TMDb API**: genre, runtime, original language, cast, release date                                                   | `/search/movie`, `/movie/{id}`                                                                  | JSON                               |
| Unstructured            | **YouTube trailer comments** (top-level, with timestamps)                                                             | `commentThreads.list` (1 unit per call, 100 per page). Cap at ~5,000 per film                   | JSON → text                        |
| Unstructured (practice) | **IMDb 50K labelled reviews** from Homework 1.2                                                                       | Local CSV                                                                                       | CSV                                |

Rules:

- Store API keys in `.env` (commit a `.env.example`, never `.env`). Add `.env` to `.gitignore`.
- Track YouTube quota usage (10,000 units/day) and print it after each pull.
- Respect rate limits with sleeps and retries. **Do not scrape IMDb, Sacnilk or anything behind a login.**
- **Privacy:** drop author names, channel IDs and profile URLs from comments before saving anything to `data/clean/`. Raw files containing them stay in `data/raw/`, which is gitignored. Commit only a download script and a hashed or anonymised sample.
- Reddit is optional and should be skipped by default, since API access needs approval. Mention it in the limitations section instead.

## 3. Repo structure

```
release-day-radar/
├── README.md                 # setup → run everything → outputs; repo link
├── MANUAL_STEPS.md           # living checklist (see §0)
├── QA_PREP.md                # plain-English explanation of every step + likely viva questions
├── requirements.txt
├── .env.example
├── Makefile                  # make all / make collect / make clean / make spark / make charts / make report
├── docs/brief_case_A.pdf
├── data/
│   ├── raw/                  # untouched API/CSV pulls (gitignored if large/private)
│   ├── interim/              # flattened JSON
│   ├── clean/                # final cleaned tables
│   └── manual/               # Google Trends CSVs, spreadsheet exports, film list
├── src/
│   ├── 01_collect_wikipedia.py
│   ├── 02_collect_tmdb.py
│   ├── 03_collect_youtube.py
│   ├── 04_flatten_json.py    # pd.json_normalize
│   ├── 05_match_films.py     # canonical film_id across sources
│   ├── 06_clean_typecast.py  # ₹ Cr parsing, dates, counts
│   ├── 07_sentiment.py       # VADER: validate on IMDb 50K, then apply
│   ├── 08_spark_text_job.py  # PySpark ≥50k rows
│   ├── 09_load_mysql.py
│   ├── 10_analysis.py        # normalisation, correlations, buzz index
│   └── 11_charts.py
├── sql/
│   ├── schema.sql
│   └── queries.sql           # ≥5 queries incl. JOIN + GROUP BY, each with a comment on what it answers
├── notebooks/
│   ├── spark_text_job.ipynb  # same as script, with outputs saved
│   └── exploration.ipynb
├── outputs/
│   ├── charts/               # PNGs, titled with findings
│   ├── tables/               # csvs used in the report
│   └── cleaning_log.csv
└── report/
    ├── report.md             # → report.docx / report.pdf via pandoc
    ├── slides.md             # → slides.pptx via pandoc (≤10 slides)
    ├── er_diagram.png        # generated (e.g. from a Mermaid/graphviz source in report/er_diagram.mmd)
    └── appendix_ai_use.md
```

## 4. Technical requirements — build every one (mapped to evidence)

1. **Data types:** produce `outputs/tables/data_inventory.csv` covering every field used, with columns: field, table, example, nominal/ordinal/discrete/continuous, structured/semi/unstructured, source. Include it in the report as a table.
2. **3 Vs (V profile):** compute the real numbers, not estimates where you can measure them: rows and MB per source, the number of formats, and velocity (e.g. comments per hour in the first 72 h after trailer launch, from comment timestamps; also Google Trends rise and decay). Make one chart of comment velocity over time. Write a one-page "V profile" that says which V dominated (expected: Variety) and how it changed our tool choices.
3. **Source register:** `outputs/tables/source_register.csv` with URL, access date, method, terms-of-use link and a one-line note, filled in automatically from collection logs.
4. **Formats:** flatten JSON with `pd.json_normalize`, showing a before and after example in the report. Load MySQL with at least these tables:
   - `films(film_id PK, title_clean, language, genre, runtime_min, release_date, budget_cr, tmdb_id)`
   - `trailers(trailer_id PK, film_id FK, youtube_video_id, publish_ts, views, likes, comment_count)`
   - `box_office(film_id FK, metric, value_cr, source)` — opening weekend, gross, etc.
   - `comments(comment_id PK, film_id FK, published_ts, text_clean, length, vader_compound)` (no usernames)
   - `trends_daily(film_id FK, date, interest)`

   Generate the ER diagram. Write `sql/queries.sql` with at least 5 working queries, including a JOIN and a GROUP BY. Run them and save their outputs.

5. **Spreadsheet vs pandas:** pick ONE cleaning step (recommended: converting "₹12.5 Cr" / "1,25,00,000" strings into crores). Do it in pandas, then create a **manual step** where I do the same thing in Google Sheets. Give me the exact formulas to paste, the file to import, and what to screenshot. Then write the side-by-side note: time taken, reproducibility, error risk, scale.
6. **Missing values:** find the gaps (missing screens or budget, films without some box-office metric, deleted or empty comments, missing Trends days). For each one, decide drop, fill or keep, and justify it in the cleaning log.
7. **Type casting:** handle ₹ Cr, lakh-style Indian digit grouping, "crore" in words, USD figures (decide whether to convert or exclude, and log it), text dates to `datetime`, ISO-8601 YouTube timestamps to IST, and counts stored as text to int.
8. **Film-name matching:** build a canonical `film_id`. Normalise titles (lowercase, strip years in parentheses, strip "Official Trailer", "Teaser", language tags and punctuation), then use fuzzy matching (`rapidfuzz`) with a threshold. **Print any match below 95 for me to confirm (manual step).** Log every match decision.
9. **Normalisation:** z-score or min-max views and collections, and compute per-screen figures if screens are available. At least one chart must use normalised values.
10. **PySpark:** run on at least 50,000 rows (our comments plus the IMDb 50K corpus, tagged `source`). The job should clean the text, measure length, count terms (top terms per film, excluding stopwords), and aggregate by film and source. Print row counts before and after each stage. Provide both a script and a notebook with saved outputs. Run in local mode.
11. **Sentiment:** validate VADER on the labelled IMDb 50K first and report its accuracy and F1. Then apply it to the trailer comments. Note the limits (Hinglish, sarcasm, emojis).
12. **Cleaning log:** `outputs/cleaning_log.csv`, with one row per decision: `id, stage, problem_found, rows_affected, action_taken, why`. Each script appends its own rows automatically, with real counts. This is the most important Module 1 evidence, so be thorough. Aim for 15 or more real entries.
13. **Reproducibility:** `make all` should rebuild everything from raw data to charts. The README must let an outsider rerun it all, including how to get the keys and download the raw data.

**Beyond the minimum (do at least one):**

- A **Buzz Index**: a weighted combination of normalised trailer views, like ratio, comment velocity and sentiment. Fit it on all films except one, then test whether it would have called the held-out film. Report the result honestly, even if it fails.
- **Aspect analysis**: keyword groups (music, story, acting, VFX, length) and how their mentions and sentiment shift before and after release.
- **Bot/paid-buzz check**: bursts of near-identical comments, found with hashed text and timestamps.

## 5. Analysis and honesty rules

- Rank correlation (Spearman) between trailer-week engagement and opening weekend, with n stated on every chart. With only ~12 films, **say clearly that this is weak evidence and not causal**. Name the confounders: star power, screen count, holiday release, franchise status, budget and marketing spend, and Hindi vs regional differences.
- Make at least 3 original charts, with **at least 1 combining two sources**. **Every chart title states the finding** (e.g. "Trailer views tracked opening weekends loosely (ρ = 0.xx, n = 12)"), not a label like "Views vs Collections". Fill in the real numbers.
- The recommendation must follow from the evidence, e.g. a rule of thumb for the Saturday-morning screen decision, with its uncertainty stated.

## 6. Phases (match the brief's check-ins)

**Phase 1 — Frame**

- Set up the repo, venv and requirements, and write `MANUAL_STEPS.md`.
- Manual steps:
  - **M1:** Get a YouTube Data API key (Google Cloud Console → new project → enable "YouTube Data API v3" → Credentials → API key) and put it in `.env` as `YT_API_KEY`.
  - **M2:** Get a TMDb API key (themoviedb.org → account → Settings → API → request a developer key), stored as `TMDB_API_KEY`.
  - **M3:** Install MySQL 8 locally or with Docker (give me both options, with a `docker run` one-liner), and create a user and DB, with credentials in `.env`.
  - **M4:** Copy the IMDb 50K CSV from Homework 1.2 to `data/manual/imdb_50k.csv`.
  - **M5:** Create the GitHub repo, add every teammate as a collaborator, and push.
- Test that every source returns data for one film.
- **M6:** Approve the film list.
- Write `report/phase1_checkin.md`: one paragraph with the question, decision, films and confirmed sources.

**Phase 2 — Collect and model**

- Pull everything and flatten the JSON. Load MySQL, generate the ER diagram, and record row counts per table.
- Write the source register and V profile.
- **M7:** Export Google Trends CSVs. Give me the exact settings: region India, the date range per film, the search term to use, and the file names to save as `data/manual/trends_<film_id>.csv`.
- **M8:** Each teammate makes at least one meaningful commit (suggest a specific small task for each person, e.g. one adds 1 SQL query, one writes a source-register note, one adds the spreadsheet screenshot).

**Phase 3 — Clean and analyse**

- Match titles (**M9:** confirm uncertain matches). Clean and type-cast, run sentiment and the PySpark job, and run the analysis and charts.
- **M10:** Do the spreadsheet cleaning step in Google Sheets (exact instructions plus screenshots into `report/img/`).
- Produce the cleaning log and at least 2 finding-titled charts for the check-in.

**Phase 4 — Story and submit**

- Write the report, slides, README, `QA_PREP.md`, and the AI-use appendix.
- **M11:** Fill in the team contribution split (names, roles, %) in the format shown in class. Give me a template file.
- **M12:** Each member reads `QA_PREP.md`, and we rehearse the 7-minute talk. Give me a slide-by-slide speaker script with timings and who presents what.
- Build the final zip `TeamName_FinalSubmission.zip` containing the report, slides, code, data (cleaned data, or a sample if over 50 MB), the README and the contribution split. **M13:** Rename it with our team name and submit.

## 7. The report (`report/report.md` → `.docx` and `.pdf`, 10 pages max plus appendices)

Follow this **exact order** from the brief:

a. **Executive summary:** the answer for the Head of Distribution in exactly 3 sentences, in plain language with no jargon.
b. **Question and why it matters:** tie it to the screens/promotion decision.
c. **Data inventory and V profile:** the inventory table, plus the one-page V profile with real numbers.
d. **Pipeline:** a diagram from source to chart (generated), plus a short description of each stage.
e. **Cleaning log:** the full table (move the overflow to an appendix if it's long) and a short narrative of the 4–5 most important decisions.
f. **Findings:** at least 3 original charts with finding titles, at least 1 combining two sources and at least 1 normalised. Give each chart 2–3 sentences: what it shows, how sure we are, and the n.
g. **Recommendation for next Friday:** concrete and actionable, with its conditions.
h. **Limitations and bias:** sample size, who writes YouTube comments, paid promotion and bots, regional vs Hindi coverage, the reliability of box-office figures (producer-reported vs trade), VADER's limits on Hinglish, and missing Reddit data.
i. **Reflection:** how our question changed as we explored (write it from what actually happened in this build, so keep notes as you go in `report/reflection_notes.md`), and what we'd do with better data.

**Appendices:** the ER diagram and schema SQL, the 5+ queries with their outputs, PySpark row counts, the spreadsheet-vs-pandas note with screenshots, the source register, and the **AI-use disclosure** (tools used, what we asked, what we changed; leave clearly marked spaces for us to add our own edits).

Writing style: written for a non-technical executive, short sentences, active voice. Mark any place where I need to add something with `[[TODO-HUMAN: …]]`, and list all of them at the end of your final summary.

## 8. Slides (`report/slides.md` → `.pptx`, 10 slides max, 7 minutes)

Open with the answer, then the evidence. One idea per slide, a finding as each slide title, readable at a glance. Suggested order: 1 answer · 2 the decision and question · 3 data and V profile · 4 the join problem and how we fixed it · 5 key cleaning decisions · 6 finding 1 · 7 finding 2 (two sources combined) · 8 finding 3 / buzz index · 9 recommendation · 10 limits and what's next. Add speaker notes.

## 9. `QA_PREP.md` (critical — every member gets grilled)

For each script: what it does, the 3 most important lines and why, and what would break if they were removed. Then add 25 likely viva questions with short answers, e.g. "Why Spearman and not Pearson?", "Why z-score here?", "Why did you drop X rows?", "What is json_normalize doing?", "Why PySpark for 50k rows?", "Explain your JOIN query", "Is this causal?", "How did you match film names?", "Why VADER?", "What's ordinal vs nominal in your data?"

## 10. Finish

When everything is done, print:

1. A table showing every rubric line (15 marks), the file(s) that satisfy it, and ✅/⚠️.
2. Any unfinished MANUAL steps.
3. All `[[TODO-HUMAN]]` markers.
4. The exact commands to rebuild from scratch.

Start now with Phase 1: read the brief, set up the repo, write `MANUAL_STEPS.md`, then stop at the first manual step.
