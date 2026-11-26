"""
One place that decides how tables look in the report, so every table follows the same rules:
  - plain-English column headers (no snake_case)
  - whole numbers with thousands separators (350,426), shares as percentages (78.1%)
  - numbers right-aligned, text left-aligned
  - film_ids shown as film titles
"""

import pandas as pd

from utils import DATA_CLEAN


def film_names():
    """film_id → readable title, e.g. kantara_chapter_1 → Kantara: Chapter 1."""
    films = pd.read_csv(DATA_CLEAN / "films.csv")
    names = dict(zip(films.film_id, films.title_clean))
    names["imdb_50k"] = "IMDb 50K corpus"
    return names


def format_value(value, kind="auto", digits=2):
    """Format one cell. kind: 'int', 'pct', 'float' or 'auto' (guess from the value)."""
    if pd.isna(value):
        return "—"
    if isinstance(value, bool):
        return "✓" if value else "✗"
    if kind == "pct":
        return f"{value:.1%}"
    if kind == "int" or (kind == "auto" and isinstance(value, (int, float)) and float(value).is_integer()):
        return f"{int(value):,}"
    if kind in ("float", "auto") and isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def md(df, kinds=None, digits=2):
    """
    DataFrame → markdown pipe table. `kinds` maps column → 'int' / 'pct' / 'float' / 'text'.
    Numeric columns are right-aligned; everything else left-aligned.
    """
    kinds = kinds or {}
    out = df.copy()
    align = []
    for col in df.columns:
        kind = kinds.get(col, "auto")
        numeric = kind in ("int", "pct", "float") or (kind == "auto" and pd.api.types.is_numeric_dtype(df[col])
                                                       and not pd.api.types.is_bool_dtype(df[col]))
        if kind == "text":
            out[col] = df[col].astype(str)
        else:
            out[col] = [format_value(v, kind, digits) for v in df[col]]
        align.append("right" if numeric else ("center" if pd.api.types.is_bool_dtype(df[col]) else "left"))
    return out.to_markdown(index=False, colalign=align)
