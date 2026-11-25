"""Predict the sentiment of new text with the trained model.

Usage:
    python src/predict.py "The acting was brilliant and the story kept me hooked."
    python src/predict.py --file reviews.txt      # one review per line
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from preprocess import clean_text  # noqa: E402

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "sentiment_model.joblib"


def load_model(path: Path = MODEL_PATH):
    if not path.exists():
        sys.exit("Model not found. Run `python src/train.py` first.")
    return joblib.load(path)


def predict(texts: list[str], model=None) -> list[tuple[str, float]]:
    """Return (label, probability of that label) for each text."""
    model = model or load_model()
    cleaned = [clean_text(t) for t in texts]
    labels = model.predict(cleaned)
    scores = model.predict_proba(cleaned).max(axis=1)
    return [("positive" if lab == 1 else "negative", float(s)) for lab, s in zip(labels, scores)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("text", nargs="*", help="review text")
    parser.add_argument("--file", type=Path, help="file with one review per line")
    args = parser.parse_args()

    texts = list(args.text)
    if args.file:
        texts += [ln.strip() for ln in args.file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not texts:
        parser.error("give some text or --file")

    for text, (label, score) in zip(texts, predict(texts)):
        preview = text if len(text) <= 70 else text[:67] + "..."
        print(f"{label.upper():<9} ({score:.2f})  {preview}")


if __name__ == "__main__":
    main()
