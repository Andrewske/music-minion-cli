"""Strategy 1: Clean Keyword Overlap (Jaccard similarity).

Uses ONLY title + artist + filename stem (NO album).
Strips noise words, month prefixes, track numbers, then computes
Jaccard similarity on keyword sets.
"""

import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

DB_PATH = Path.home() / ".local/share/music-minion/music_minion.db"

# Noise words to strip (after tokenizing)
NOISE_WORDS = {
    "free", "download", "dl", "out", "now", "official", "full", "stream",
    "original", "mix", "audio", "video", "premiere", "exclusive", "single",
    "master", "explicit", "ep", "vol", "the", "a", "an", "feat", "ft",
    "prod", "produced", "records", "music", "release", "new", "edit",
}

# Month prefix pattern: "Nov 23_", "Dec 24_", "jan25_", etc.
_MONTH_PREFIX = re.compile(
    r"^(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*\d{2,4}[_\s-]+",
    re.IGNORECASE,
)
# Track number prefix: "01 - ", "03 ", "1. ", etc.
_TRACK_NUM_PREFIX = re.compile(r"^\d{1,3}[\s.\-_]+")


def clean_filename_stem(stem: str) -> str:
    """Strip month prefix and track number from filename stem."""
    stem = _MONTH_PREFIX.sub("", stem)
    stem = _TRACK_NUM_PREFIX.sub("", stem)
    return stem


def normalize(text: str) -> set[str]:
    """Lowercase, strip punctuation (keep &), tokenize, remove noise words."""
    if not text:
        return set()
    # Replace & with 'and' so both forms match
    text = text.replace("&", " and ")
    # Remove punctuation except alphanumerics and spaces
    text = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = text.split()
    return {t for t in tokens if t and t not in NOISE_WORDS and not t.isdigit()}


def keyword_set(track: dict, is_local: bool = False) -> set[str]:
    """Build keyword set from title + artist (+ filename stem for local tracks)."""
    parts: list[str] = []

    title = track.get("title") or ""
    artist = track.get("artist") or ""
    parts.append(title)
    parts.append(artist)

    if is_local:
        local_path = track.get("local_path") or ""
        if local_path:
            stem = Path(local_path).stem
            stem = clean_filename_stem(stem)
            parts.append(stem)

    combined = " ".join(parts)
    return normalize(combined)


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def fetch_tracks(conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    conn.row_factory = sqlite3.Row
    local_rows = conn.execute("""
        SELECT id, title, artist, album, local_path
        FROM tracks
        WHERE (source = 'local' OR source = 'file')
          AND soundcloud_id IS NULL
    """).fetchall()

    sc_rows = conn.execute("""
        SELECT id, title, artist, soundcloud_id
        FROM tracks
        WHERE source = 'soundcloud'
          AND soundcloud_id IS NOT NULL
    """).fetchall()

    return [dict(r) for r in local_rows], [dict(r) for r in sc_rows]


def match_all(
    local_tracks: list[dict],
    sc_tracks: list[dict],
) -> list[tuple[dict, dict | None, float]]:
    """For each local track, find best-scoring SC track."""
    # Pre-build SC keyword sets
    sc_kw = [(sc, keyword_set(sc, is_local=False)) for sc in sc_tracks]

    results = []
    for local in local_tracks:
        lkw = keyword_set(local, is_local=True)
        best_score = -1.0
        best_sc = None
        for sc, skw in sc_kw:
            score = jaccard(lkw, skw)
            if score > best_score:
                best_score = score
                best_sc = sc
        results.append((local, best_sc, best_score))

    return results


def bucket_name(score: float) -> str:
    if score >= 0.90:
        return "0.90+"
    elif score >= 0.80:
        return "0.80-0.89"
    elif score >= 0.70:
        return "0.70-0.79"
    elif score >= 0.60:
        return "0.60-0.69"
    elif score >= 0.50:
        return "0.50-0.59"
    else:
        return "<0.50"


BUCKET_ORDER = ["0.90+", "0.80-0.89", "0.70-0.79", "0.60-0.69", "0.50-0.59", "<0.50"]


def label(track: dict) -> str:
    return f"{track.get('artist', '?')} - {track.get('title', '?')}"


def spot_check(
    fragment: str,
    results: list[tuple[dict, dict | None, float]],
) -> None:
    fragment_lower = fragment.lower()
    matches = [
        (local, sc, score)
        for local, sc, score in results
        if fragment_lower in (local.get("title") or "").lower()
    ]
    if not matches:
        print(f"  [NOT FOUND] '{fragment}' — no local track title contains this")
        return
    for local, sc, score in matches[:3]:
        sc_label = label(sc) if sc else "NO MATCH"
        print(f"  [{score:.3f}] LOCAL: {label(local)}")
        print(f"         SC:    {sc_label}")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    local_tracks, sc_tracks = fetch_tracks(conn)
    conn.close()

    print(f"Local unlinked:  {len(local_tracks)}")
    print(f"SC tracks in DB: {len(sc_tracks)}")
    print("\nRunning Jaccard matching (brute force)...")

    results = match_all(local_tracks, sc_tracks)

    # --- Distribution ---
    counts: Counter = Counter()
    by_bucket: dict[str, list] = defaultdict(list)
    for local, sc, score in results:
        b = bucket_name(score)
        counts[b] += 1
        by_bucket[b].append((local, sc, score))

    total = len(results)
    print("\n=== CONFIDENCE DISTRIBUTION ===")
    for b in BUCKET_ORDER:
        n = counts.get(b, 0)
        pct = n / total * 100 if total else 0
        bar = "#" * int(pct / 2)
        print(f"  {b:>10}: {n:>5}  ({pct:5.1f}%)  {bar}")

    print("\n=== CUMULATIVE ===")
    cum_90 = sum(counts.get(b, 0) for b in ["0.90+"])
    cum_80 = sum(counts.get(b, 0) for b in ["0.90+", "0.80-0.89"])
    cum_70 = sum(counts.get(b, 0) for b in ["0.90+", "0.80-0.89", "0.70-0.79"])
    cum_50 = total - counts.get("<0.50", 0)
    print(f"  >= 0.90: {cum_90:>5}  ({cum_90/total*100:.1f}%)")
    print(f"  >= 0.80: {cum_80:>5}  ({cum_80/total*100:.1f}%)")
    print(f"  >= 0.70: {cum_70:>5}  ({cum_70/total*100:.1f}%)")
    print(f"  >= 0.50: {cum_50:>5}  ({cum_50/total*100:.1f}%)")

    # --- Samples ---
    print("\n=== SAMPLES (10 per bucket) ===")
    for b in BUCKET_ORDER:
        items = by_bucket[b]
        print(f"\n--- {b} ({len(items)} total) ---")
        for local, sc, score in items[:10]:
            sc_lbl = label(sc) if sc else "NO MATCH"
            print(f"  [{score:.3f}] {label(local)}")
            print(f"           → {sc_lbl}")

    # --- Spot checks ---
    print("\n=== SPOT CHECKS ===")
    spot_cases = [
        "LRAD",
        "Nap In The Club",
        "#SELFIE",
        "Hawt",
        "The Game",
        "Boss Mode",
        "Vincent",
    ]
    for fragment in spot_cases:
        print(f"\n[{fragment}]")
        spot_check(fragment, results)


if __name__ == "__main__":
    main()
