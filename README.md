# Release Day Radar — Case Study A

Data and Storytelling · Module 1. Repo: https://github.com/Shubhaditya14/Case-Study-A-Release-Day-Radar

**Question:** Did trailer-week YouTube engagement predict opening-weekend collections for 10–12 Hindi and regional films released in 2025–26 — and does audience sentiment add anything beyond raw views?

> Work in progress (Phase 1). Full setup → run → outputs instructions are completed in Phase 4.

## Setup (so far)

Requirements: macOS/Linux, [uv](https://docs.astral.sh/uv/), Java 17+ (for PySpark), Docker or MySQL 8, pandoc.

```bash
make setup                 # creates .venv (Python 3.12) and installs requirements.txt
cp .env.example .env       # then fill in the keys — see MANUAL_STEPS.md M1–M3
make smoke                 # checks Wikipedia, TMDb and YouTube each return data
```

The brief is in `docs/brief_case_A.pdf`. Manual steps (keys, approvals) are in `MANUAL_STEPS.md`.
