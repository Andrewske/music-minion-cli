"""Test script v2: keyword overlap matching vs TF-IDF.

Simple approach: split all available text into tokens, score by overlap ratio.
Compare results against TF-IDF to see which catches more correct matches.
"""

import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from music_minion.domain.library.deduplication import normalize_string

DB_PATH = Path.home() / ".local/share/music-minion/music_minion.db"

STOP_WORDS = {
    "free", "download", "dl", "out", "now", "official", "full", "stream",
    "original", "mix", "audio", "video", "premiere", "exclusive",
}


def tokenize(text: str) -> set[str]:
    """Normalize and split into unique tokens, removing stop words."""
    normalized = normalize_string(text)
    tokens = set(normalized.split())
    return tokens - STOP_WORDS


def build_track_tokens(track: dict, include_path: bool = False) -> set[str]:
    """Build token set from all available track fields."""
    parts = []
    for field in ("title", "artist", "album"):
        val = track.get(field)
        if val:
            parts.append(val)

    if include_path:
        path = track.get("local_path", "")
        if path:
            stem = Path(path).stem
            # Strip common prefixes like "Nov 23_" or "01 - "
            stem = re.sub(r"^[A-Za-z]{3,9}\s+\d{2}_", "", stem)
            stem = re.sub(r"^\d+\s*[-–]\s*", "", stem)
            parts.append(stem)

    return tokenize(" ".join(parts))


def keyword_score(local_tokens: set[str], sc_tokens: set[str]) -> float:
    """Score based on token overlap.

    Uses containment (what % of local tokens found in SC) weighted by
    Jaccard (penalize SC having lots of extra tokens = likely wrong track).
    """
    if not local_tokens or not sc_tokens:
        return 0.0

    intersection = local_tokens & sc_tokens
    if not intersection:
        return 0.0

    containment = len(intersection) / len(local_tokens)
    jaccard = len(intersection) / len(local_tokens | sc_tokens)

    # Weighted: 70% containment (did we find our words?), 30% jaccard (how much noise?)
    return 0.7 * containment + 0.3 * jaccard


def run_matching():
    conn = sqlite3.connect(DB_PATH)
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
    conn.close()

    local_tracks = [dict(r) for r in local_rows]
    sc_tracks = [dict(r) for r in sc_rows]

    print(f"Local unlinked: {len(local_tracks)}")
    print(f"SC tracks: {len(sc_tracks)}")

    # Pre-tokenize SC tracks
    print("Tokenizing SC tracks...")
    sc_token_sets = [(t, build_track_tokens(t)) for t in sc_tracks]

    print("Matching...")
    results = []
    report_interval = max(1, len(local_tracks) // 20)

    for i, lt in enumerate(local_tracks):
        if i % report_interval == 0:
            print(f"  {i}/{len(local_tracks)} ({i/len(local_tracks)*100:.0f}%)")

        local_tokens = build_track_tokens(lt, include_path=True)
        if not local_tokens:
            results.append((lt, None, 0.0))
            continue

        best_match = None
        best_score = 0.0

        for sc_t, sc_tokens in sc_token_sets:
            score = keyword_score(local_tokens, sc_tokens)
            if score > best_score:
                best_score = score
                best_match = sc_t

        results.append((lt, best_match, best_score))

    # Bucket analysis
    buckets = Counter()
    by_bucket: dict[str, list] = {
        "0.90+": [], "0.80-0.89": [], "0.70-0.79": [],
        "0.60-0.69": [], "0.50-0.59": [], "< 0.50": [],
    }

    for lt, match, score in results:
        if score >= 0.90:
            buckets["0.90+"] += 1
            by_bucket["0.90+"].append((lt, match, score))
        elif score >= 0.80:
            buckets["0.80-0.89"] += 1
            by_bucket["0.80-0.89"].append((lt, match, score))
        elif score >= 0.70:
            buckets["0.70-0.79"] += 1
            by_bucket["0.70-0.79"].append((lt, match, score))
        elif score >= 0.60:
            buckets["0.60-0.69"] += 1
            by_bucket["0.60-0.69"].append((lt, match, score))
        elif score >= 0.50:
            buckets["0.50-0.59"] += 1
            by_bucket["0.50-0.59"].append((lt, match, score))
        else:
            buckets["< 0.50"] += 1
            by_bucket["< 0.50"].append((lt, match, score))

    total = len(results)
    print("\n=== KEYWORD OVERLAP DISTRIBUTION ===")
    for bucket in ["0.90+", "0.80-0.89", "0.70-0.79", "0.60-0.69", "0.50-0.59", "< 0.50"]:
        count = buckets.get(bucket, 0)
        pct = count / total * 100
        bar = "#" * int(pct / 2)
        print(f"  {bucket:>10}: {count:>5} ({pct:5.1f}%) {bar}")

    def show(bucket_name: str, count: int = 15):
        items = by_bucket.get(bucket_name, [])
        print(f"\n=== {bucket_name} — {len(items)} total, showing {min(count, len(items))} ===")
        for lt, match, score in items[:count]:
            local_label = f"{lt.get('artist', '?')} - {lt.get('title', '?')}"
            sc_label = f"{match['artist']} - {match['title']}" if match else "NO MATCH"

            local_tokens = build_track_tokens(lt, include_path=True)
            sc_tokens = build_track_tokens(match) if match else set()
            shared = local_tokens & sc_tokens
            only_local = local_tokens - sc_tokens
            only_sc = sc_tokens - local_tokens

            print(f"  [{score:.3f}] {local_label}")
            print(f"           {sc_label}")
            print(f"           shared={shared}  miss={only_local}  extra={only_sc}")

    show("0.90+", 8)
    show("0.80-0.89", 15)
    show("0.70-0.79", 15)
    show("0.60-0.69", 15)
    show("0.50-0.59", 10)

    # Spot-check: problematic cases from TF-IDF
    print("\n=== SPOT CHECK: TF-IDF problem cases ===")
    problem_titles = [
        "LRAD",  # Knife Party - LRAD matched wrong remix
        "Nap In The Club (Two Owls Remix)",  # matched Original Mix
        "#SELFIE",  # totally wrong
        "Hawt",  # Brillz - Hawt
        "The Game",  # Curfew - The Game matched Jauz
    ]
    for title_fragment in problem_titles:
        for lt, match, score in results:
            if title_fragment.lower() in (lt.get("title", "") or "").lower():
                local_label = f"{lt.get('artist', '?')} - {lt.get('title', '?')}"
                sc_label = f"{match['artist']} - {match['title']}" if match else "NO MATCH"
                print(f"  [{score:.3f}] {local_label}")
                print(f"           {sc_label}")
                break


if __name__ == "__main__":
    run_matching()
