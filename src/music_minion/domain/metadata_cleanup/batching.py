"""Group records into batches of related tracks via shared rare keywords.

Tracks sharing an uploader, artist, or distinctive title word land together,
so the model can see e.g. two 'Chase & Status' tracks and keep the duo whole.
"""

import math
import re
from collections import Counter
from typing import Any

Record = dict[str, Any]

_WORD_RE = re.compile(r"[\w&$']+", re.UNICODE)
_STOPWORDS = {
    "the", "and", "feat", "featuring", "remix", "flip", "edit", "bootleg", "vip",
    "free", "download", "out", "now", "mix", "with", "for", "you", "official",
    "records", "recordings", "music", "extended", "version", "rework", "premiere",
}  # fmt: skip


def record_text(record: Record) -> str:
    sc = record.get("soundcloud") or {}
    tags = record.get("file_tags") or {}
    parts = [record.get("filename", ""), sc.get("title", ""), sc.get("uploader", "")]
    parts += [sc.get("metadata_artist", ""), tags.get("artist", "")]
    return " ".join(part for part in parts if part)


def keywords(record: Record) -> set[str]:
    words = {word.lower().strip("'") for word in _WORD_RE.findall(record_text(record))}
    return {word for word in words if len(word) >= 3 and word not in _STOPWORDS}


def idf_weights(keyword_sets: list[set[str]]) -> dict[str, float]:
    """Words shared by 2+ tracks get weight; unique words are useless for grouping."""
    counts = Counter(word for words in keyword_sets for word in words)
    total = len(keyword_sets)
    return {word: math.log(total / n) for word, n in counts.items() if n >= 2}


def _best_match(
    batch_words: set[str], pool: list[int], kw: list[set[str]], idf: dict
) -> int:
    """Index into pool of the most related remaining record (0 if none related)."""
    scores = [sum(idf.get(w, 0.0) for w in kw[i] & batch_words) for i in pool]
    best = max(range(len(pool)), key=lambda p: scores[p])
    return best if scores[best] > 0 else 0


def make_batches(records: list[Record], size: int = 10) -> list[list[Record]]:
    """Greedy fill: seed a batch, then add the most keyword-related record."""
    kw = [keywords(record) for record in records]
    idf = idf_weights(kw)
    pool = list(range(len(records)))
    batches: list[list[Record]] = []
    while pool:
        batch = [pool.pop(0)]
        words = set(kw[batch[0]])
        while pool and len(batch) < size:
            chosen = pool.pop(_best_match(words, pool, kw, idf))
            batch.append(chosen)
            words |= kw[chosen]
        batches.append([records[i] for i in batch])
    return batches
