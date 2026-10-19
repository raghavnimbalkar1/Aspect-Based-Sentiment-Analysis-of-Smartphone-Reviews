from __future__ import annotations

import hashlib
import re
from functools import lru_cache

import pysbd
from langdetect import DetectorFactory, LangDetectException, detect

from smartphone_absa.domain import Sentence

DetectorFactory.seed = 0
_segmenter = pysbd.Segmenter(language="en", clean=False, char_span=True)


def text_hash(text: str) -> str:
    """Stable duplicate grouping; never replace the original evidence text."""
    normalised = " ".join(text.casefold().split())
    return hashlib.sha256(normalised.encode()).hexdigest()


@lru_cache(maxsize=8192)
def detect_language(text: str) -> str:
    letters = re.sub(r"[^\w]", "", text, flags=re.UNICODE)
    if len(letters) < 20:
        return "unknown"
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"


def split_sentences(text: str, review_id: str = "input") -> list[Sentence]:
    result = []
    for span in _segmenter.segment(text):
        start, end = span.start, span.end
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            result.append(
                Sentence(
                    id=f"{review_id}:{start}:{end}", text=text[start:end], start=start, end=end
                )
            )
    return result
