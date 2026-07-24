"""Test script: match unlinked local tracks to SoundCloud tracks in DB.

No API calls needed — both sets already in the database.
Uses existing TF-IDF matching from deduplication.py.
Outputs detailed quality analysis to help decide auto-link threshold.
"""

import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from music_minion.domain.library.deduplication import find_best_matches_tfidf


DB_PATH = Path.home() / ".local/share/music-minion/music_minion.db"


def fetch_tracks(conn: sqlite3.Connection) -> tuple[list, list]:
    conn.row_factory = sqlite3.Row

    local_rows = conn.execute("""
        SELECT id, title, artist, album, local_path, soundcloud_id
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


def run_matching():
    conn = sqlite3.connect(DB_PATH)
    local_tracks, sc_tracks_raw = fetch_tracks(conn)
    conn.close()

    print(f"Local unlinked: {len(local_tracks)}")
    print(f"SC tracks in DB: {len(sc_tracks_raw)}")
    print()

    local_as_queries = [(str(t["id"]), t) for t in local_tracks]
    sc_as_index = list(sc_tracks_raw)
    local_by_id = {str(t["id"]): t for t in local_tracks}

    print("Running TF-IDF matching...")
    results = find_best_matches_tfidf(local_as_queries, sc_as_index, min_score=0.3)

    # Bucket results
    buckets = Counter()
    by_bucket: dict[str, list] = {
        "0.95+": [], "0.85-0.94": [], "0.70-0.84": [],
        "0.50-0.69": [], "0.30-0.49": [], "< 0.30": [],
    }

    for local_id, match, score in results:
        if match is None or score < 0.30:
            buckets["< 0.30"] += 1
            by_bucket["< 0.30"].append((local_id, match, score))
        elif score >= 0.95:
            buckets["0.95+"] += 1
            by_bucket["0.95+"].append((local_id, match, score))
        elif score >= 0.85:
            buckets["0.85-0.94"] += 1
            by_bucket["0.85-0.94"].append((local_id, match, score))
        elif score >= 0.70:
            buckets["0.70-0.84"] += 1
            by_bucket["0.70-0.84"].append((local_id, match, score))
        elif score >= 0.50:
            buckets["0.50-0.69"] += 1
            by_bucket["0.50-0.69"].append((local_id, match, score))
        else:
            buckets["0.30-0.49"] += 1
            by_bucket["0.30-0.49"].append((local_id, match, score))

    total = len(results)
    print("\n=== CONFIDENCE DISTRIBUTION ===")
    for bucket in ["0.95+", "0.85-0.94", "0.70-0.84", "0.50-0.69", "0.30-0.49", "< 0.30"]:
        count = buckets.get(bucket, 0)
        pct = count / total * 100 if total else 0
        bar = "#" * int(pct / 2)
        print(f"  {bucket:>10}: {count:>5} ({pct:5.1f}%) {bar}")

    matched_50 = sum(buckets.get(b, 0) for b in ["0.95+", "0.85-0.94", "0.70-0.84", "0.50-0.69"])
    matched_70 = sum(buckets.get(b, 0) for b in ["0.95+", "0.85-0.94", "0.70-0.84"])
    matched_85 = sum(buckets.get(b, 0) for b in ["0.95+", "0.85-0.94"])
    print(f"\n  >= 0.85: {matched_85} ({matched_85/total*100:.1f}%)")
    print(f"  >= 0.70: {matched_70} ({matched_70/total*100:.1f}%)")
    print(f"  >= 0.50: {matched_50} ({matched_50/total*100:.1f}%)")

    def show_samples(bucket_name: str, count: int = 15):
        items = by_bucket.get(bucket_name, [])
        print(f"\n=== {bucket_name} — {len(items)} total, showing {min(count, len(items))} ===")
        for local_id, match, score in items[:count]:
            lt = local_by_id.get(local_id, {})
            local_label = f"{lt.get('artist', '?')} - {lt.get('title', '?')}"
            sc_label = f"{match['artist']} - {match['title']}" if match else "NO MATCH"
            print(f"  [{score:.3f}] {local_label}")
            print(f"           {sc_label}")

    show_samples("0.95+", 5)
    show_samples("0.85-0.94", 15)
    show_samples("0.70-0.84", 20)
    show_samples("0.50-0.69", 20)
    show_samples("0.30-0.49", 10)


if __name__ == "__main__":
    run_matching()
