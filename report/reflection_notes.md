# Reflection notes (kept as we go — feeds report section i)

Dated, factual notes on what changed and why. Written during the build, not afterwards.

- **2026-11-26 (Phase 1)** — Started from question-bank Q1 (trailer engagement → opening weekend), with a sentiment add-on: "does sentiment add anything beyond raw views?". Wikipedia MediaWiki API confirmed working for the test film (Chhaava — infobox has a Box office row). TMDb and YouTube waiting on keys.
- **2026-11-26 (Phase 1)** — Tooling choice: Python 3.12 venv (not the system 3.14) because PySpark 3.5 does not yet support 3.14. Spark local mode confirmed running on Java 21.
- **2026-11-26 (Phase 1)** — Port 3306 was already used by a pre-installed MySQL, so the project's MySQL 8.0 runs in Docker on host port 3307. Lesson: check ports before assuming defaults.
- **2026-11-26 (Phase 1)** — IMDb 50K check: 50,000 rows, perfectly balanced 25k/25k, 0 nulls, but 418 duplicate review texts — to be logged and decided in the cleaning stage.
- **2026-11-26 (Phase 1, film list)** — Big finding: Wikipedia does not report "opening weekend" consistently. Of 18 candidates, only 10 state a first-weekend figure; others give opening *day* only, or nothing. The figures also mix worldwide gross vs India net, 3-day vs 4-day (Thursday) weekends, ₹ ranges, and one is in USD. This forced decisions on the outcome metric (per-day weekend average, flags for domestic-only/USD) before any analysis.
- **2026-11-26 (Phase 1, trailers)** — Pan-India films release one trailer per language (Kantara: Chapter 1 = Hindi 39.6M, Kannada 23.9M, Telugu 18.6M views on the same day). Counting only one version would undercount regional films. Also the naive "most-viewed trailer" search picked wrong videos twice (a 2026 OTT trailer for Sitaare Zameen Par; the sequel's trailer for Dhurandhar) — trailer search must be limited to before the release date.
- **2026-11-26 (Phase 1)** — Wikipedia returned HTTP 429 until requests carried a descriptive User-Agent with a contact URL.
