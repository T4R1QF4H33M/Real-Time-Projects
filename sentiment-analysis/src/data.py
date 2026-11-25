"""Download and load the Cornell Movie Review Polarity dataset (Pang & Lee, 2004).

2,000 full-length movie reviews: 1,000 positive and 1,000 negative.
The corpus is fetched from the NLTK data mirror on first run and cached in ./data.
"""
from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

DATA_URL = (
    "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/"
    "packages/corpora/movie_reviews.zip"
)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CORPUS_DIR = DATA_DIR / "movie_reviews"


def download(force: bool = False) -> Path:
    """Download and extract the corpus if it is not already cached."""
    if CORPUS_DIR.exists() and not force:
        return CORPUS_DIR
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading dataset from {DATA_URL} ...")
    with urllib.request.urlopen(DATA_URL, timeout=120) as resp:
        payload = resp.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        zf.extractall(DATA_DIR)
    return CORPUS_DIR


def load_reviews() -> pd.DataFrame:
    """Return a DataFrame with columns: text, label (1 = positive, 0 = negative), file."""
    corpus = download()
    rows = []
    for label_name, label in (("pos", 1), ("neg", 0)):
        for path in sorted((corpus / label_name).glob("*.txt")):
            rows.append(
                {
                    "text": path.read_text(encoding="utf-8", errors="ignore"),
                    "label": label,
                    "file": path.name,
                }
            )
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError(f"No reviews found under {corpus}")
    return df


if __name__ == "__main__":
    df = load_reviews()
    print(df["label"].value_counts().rename({1: "positive", 0: "negative"}))
    print(f"Average review length: {df['text'].str.split().str.len().mean():.0f} words")
