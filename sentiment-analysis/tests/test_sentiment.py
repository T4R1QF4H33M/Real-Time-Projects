import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from preprocess import clean_text  # noqa: E402


def test_lowercases_and_strips_punctuation():
    assert clean_text("GREAT Movie!!!") == "great movie"


def test_removes_html_and_urls():
    out = clean_text("<br/>Loved it http://example.com")
    assert "br" not in out.split()
    assert "http" not in out
    assert "loved" in out


def test_keeps_negations():
    assert clean_text("This was not good") == "not good"
    assert clean_text("I didn't like it") == "not like"
    assert clean_text("I won't watch it") == "not watch"


def test_drops_stop_words():
    assert clean_text("the plot of the film") == "plot film"


def test_handles_empty_text():
    assert clean_text("") == ""


MODEL = Path(__file__).resolve().parent.parent / "models" / "sentiment_model.joblib"


@pytest.mark.skipif(not MODEL.exists(), reason="run src/train.py first")
def test_model_gets_obvious_cases_right():
    from predict import predict

    results = predict([
        "An outstanding, brilliant film with superb performances. A masterpiece.",
        "Boring, dull and badly acted. The worst movie I have seen, a total waste of time.",
    ])
    assert results[0][0] == "positive"
    assert results[1][0] == "negative"
