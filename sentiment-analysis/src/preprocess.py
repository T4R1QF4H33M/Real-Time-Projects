"""Text cleaning used before vectorisation."""
from __future__ import annotations

import re

# A small stop-word list. Negations ("not", "no", "never", ...) are deliberately
# kept because they flip sentiment ("not good" vs "good").
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "so", "of", "at", "by",
    "for", "with", "about", "to", "from", "in", "on", "is", "are", "was", "were",
    "be", "been", "being", "it", "its", "this", "that", "these", "those", "i",
    "me", "my", "we", "our", "you", "your", "he", "him", "his", "she", "her",
    "they", "them", "their", "as", "into", "than", "too", "very", "s", "t",
    "can", "will", "just", "do", "does", "did", "has", "have", "had", "what",
    "which", "who", "whom", "there", "here", "when", "where", "why", "how",
}

NEGATIONS = {"not", "no", "never", "nor", "cannot"}

_HTML = re.compile(r"<[^>]+>")
_URL = re.compile(r"https?://\S+|www\.\S+")
_NON_ALPHA = re.compile(r"[^a-z\s']")
_SPACES = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Lower-case, strip HTML/URLs/punctuation, expand n't, drop stop words."""
    text = text.lower()
    text = _HTML.sub(" ", text)
    text = _URL.sub(" ", text)
    text = text.replace("won't", "will not").replace("can't", "can not").replace("n't", " not")
    text = _NON_ALPHA.sub(" ", text)
    text = text.replace("'", " ")
    tokens = [
        tok for tok in _SPACES.split(text)
        if tok and (tok in NEGATIONS or (tok not in STOP_WORDS and len(tok) > 1))
    ]
    return " ".join(tokens)
