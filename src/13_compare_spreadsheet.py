"""
Step 13 — Spreadsheet vs pandas: compare the Google Sheets result of the "₹ text → crore" step
(manual step M10) with what pandas produced for exactly the same strings.

Input : data/manual/spreadsheet_step_output.csv  (exported from Google Sheets, has a sheet_crore column)
        data/clean/spreadsheet_step_pandas_answer.csv  (written by step 06)
Output: outputs/tables/spreadsheet_vs_pandas.csv  — one row per string, with agree / disagree
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import DATA_CLEAN, DATA_MANUAL, OUT_TABLES  # noqa: E402


def main():
    sheet_path = DATA_MANUAL / "spreadsheet_step_output.csv"
    if not sheet_path.exists():
        print("No Google Sheets export yet (manual step M10) — skipping comparison.")
        return
    sheet = pd.read_csv(sheet_path)
    pandas_answer = pd.read_csv(DATA_CLEAN / "spreadsheet_step_pandas_answer.csv")
    both = pandas_answer.merge(sheet[["id", "sheet_crore"]], on="id", how="left")
    both["sheet_crore"] = pd.to_numeric(both["sheet_crore"], errors="coerce")
    both["agree"] = (both["sheet_crore"] - both["pandas_crore"]).abs() < 0.01
    both.to_csv(OUT_TABLES / "spreadsheet_vs_pandas.csv", index=False)
    print(f"Agree on {both.agree.sum()}/{len(both)} strings")
    if (~both.agree).any():
        print(both[~both.agree][["id", "raw_text", "pandas_crore", "sheet_crore"]].to_string(index=False))


if __name__ == "__main__":
    main()
