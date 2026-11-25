"""Extract: read raw CSV extracts as strings (types are fixed in transform)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df["source_file"] = path.name
    return df


def extract_sales(raw_dir: Path, pattern: str = "sales_*.csv") -> pd.DataFrame:
    files = sorted(raw_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no files matching {pattern} in {raw_dir}")
    return pd.concat([read_csv(f) for f in files], ignore_index=True)
