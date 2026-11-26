# Reflection notes (kept as we go — feeds report section i)

Dated, factual notes on what changed and why. Written during the build, not afterwards.

- **2026-11-26 (Phase 1)** — Started from question-bank Q1 (trailer engagement → opening weekend), with a sentiment add-on: "does sentiment add anything beyond raw views?". Wikipedia MediaWiki API confirmed working for the test film (Chhaava — infobox has a Box office row). TMDb and YouTube waiting on keys.
- **2026-11-26 (Phase 1)** — Tooling choice: Python 3.12 venv (not the system 3.14) because PySpark 3.5 does not yet support 3.14. Spark local mode confirmed running on Java 21.
- **2026-11-26 (Phase 1)** — Port 3306 was already used by a pre-installed MySQL, so the project's MySQL 8.0 runs in Docker on host port 3307. Lesson: check ports before assuming defaults.
- **2026-11-26 (Phase 1)** — IMDb 50K check: 50,000 rows, perfectly balanced 25k/25k, 0 nulls, but 418 duplicate review texts — to be logged and decided in the cleaning stage.
