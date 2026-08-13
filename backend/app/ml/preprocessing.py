"""Text preprocessing for intent classification."""

import re


def preprocess_text(text: str) -> str:
    """Normalize user questions before TF-IDF vectorization."""
    if not text:
        return ""

    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s?]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
