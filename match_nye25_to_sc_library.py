#!/usr/bin/env python3
"""
Match NYE25 playlist tracks to SoundCloud tracks already in the database.
More accurate than global search since we match against user's actual library.
"""

from rapidfuzz import fuzz
from music_minion.core.database import get_db_connection
from music_minion.domain.playlists import crud


def normalize(s: str) -> str:
    """Normalize string for matching."""
    if not s:
        return ""
    return s.lower().strip()


def get_soundcloud_library() -> list[dict]:
    """Get all SoundCloud tracks from database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, artist, soundcloud_id, duration
            FROM tracks
            WHERE source = 'soundcloud' AND soundcloud_id IS NOT NULL
        """)
        return [dict(row) for row in cursor.fetchall()]


def match_track(local_track: dict, sc_library: list[dict]) -> tuple[dict | None, float, list]:
    """
    Match a local track to SoundCloud library using fuzzy matching.

    Returns: (best_match, confidence, top_candidates)
    """
    local_title = normalize(local_track.get("title", ""))
    local_artist = normalize(local_track.get("artist", ""))

    # Skip if no title
    if not local_title or local_title == "unknown":
        return None, 0.0, []

    # Score all SoundCloud tracks
    candidates = []
    for sc_track in sc_library:
        sc_title = normalize(sc_track.get("title", ""))
        sc_artist = normalize(sc_track.get("artist", ""))

        # Title similarity (most important)
        title_score = fuzz.token_set_ratio(local_title, sc_title) / 100

        # Artist similarity
        artist_score = fuzz.token_set_ratio(local_artist, sc_artist) / 100 if local_artist and local_artist != "none" else 0.5

        # Combined score (title weighted more heavily)
        combined = title_score * 0.7 + artist_score * 0.3

        # Bonus if title contains exact match of key words
        local_words = set(local_title.split())
        sc_words = set(sc_title.split())
        overlap = len(local_words & sc_words) / max(len(local_words), 1)
        combined = combined * 0.8 + overlap * 0.2

        if combined > 0.4:  # Only keep reasonable candidates
            candidates.append({
                "track": sc_track,
                "score": combined,
                "title_score": title_score,
                "artist_score": artist_score,
            })

    # Sort by score
    candidates.sort(key=lambda x: x["score"], reverse=True)

    if candidates:
        best = candidates[0]
        return best["track"], best["score"], candidates[:5]

    return None, 0.0, []


def main():
    playlist_name = "NYE25"
    min_confidence = 0.65

    print(f"Loading playlist: {playlist_name}")
    playlist = crud.get_playlist_by_name(playlist_name)
    if not playlist:
        print(f"Playlist '{playlist_name}' not found")
        return

    local_tracks = crud.get_playlist_tracks(playlist["id"])
    print(f"Found {len(local_tracks)} local tracks")

    print("\nLoading SoundCloud library...")
    sc_library = get_soundcloud_library()
    print(f"Found {len(sc_library)} SoundCloud tracks in your library")

    # Match tracks
    matched = []
    low_confidence = []
    unmatched = []

    for i, local_track in enumerate(local_tracks):
        title = local_track.get("title", "Unknown")
        artist = local_track.get("artist", "Unknown")

        best_match, confidence, candidates = match_track(local_track, sc_library)

        print(f"\n[{i+1}/{len(local_tracks)}] {artist} - {title}")

        if best_match and confidence >= min_confidence:
            matched.append({
                "local": local_track,
                "soundcloud": best_match,
                "confidence": confidence,
            })
            print(f"  ✅ MATCH [{confidence:.2f}]: {best_match['artist']} - {best_match['title']}")
        elif best_match and confidence >= 0.5:
            low_confidence.append({
                "local": local_track,
                "soundcloud": best_match,
                "confidence": confidence,
                "candidates": candidates,
            })
            print(f"  ⚠️  LOW [{confidence:.2f}]: {best_match['artist']} - {best_match['title']}")
            if len(candidates) > 1:
                print(f"     Other candidates:")
                for c in candidates[1:3]:
                    print(f"       [{c['score']:.2f}] {c['track']['artist']} - {c['track']['title']}")
        else:
            unmatched.append(local_track)
            print(f"  ❌ NO MATCH")
            if candidates:
                print(f"     Best candidate [{candidates[0]['score']:.2f}]: {candidates[0]['track']['artist']} - {candidates[0]['track']['title']}")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total local tracks: {len(local_tracks)}")
    print(f"Matched (>={min_confidence}): {len(matched)}")
    print(f"Low confidence (0.5-{min_confidence}): {len(low_confidence)}")
    print(f"Unmatched: {len(unmatched)}")

    # Save matched IDs
    all_matched_ids = [m["soundcloud"]["soundcloud_id"] for m in matched]

    print(f"\n\nMatched SoundCloud IDs saved to: matched_sc_ids.txt")
    with open("matched_sc_ids.txt", "w") as f:
        f.write("# High confidence matches\n")
        for m in matched:
            f.write(f"{m['soundcloud']['soundcloud_id']}  # {m['local']['title']}\n")

        f.write("\n# Low confidence (uncomment to include)\n")
        for m in low_confidence:
            f.write(f"# {m['soundcloud']['soundcloud_id']}  # [{m['confidence']:.2f}] {m['local']['title']} -> {m['soundcloud']['title']}\n")

    # Interactive mode for low confidence
    if low_confidence:
        print(f"\n\nReview {len(low_confidence)} low-confidence matches? (y/n): ", end="")
        try:
            response = input().strip().lower()
            if response == 'y':
                print("\nFor each track, enter 'y' to accept, 'n' to reject, or number to select alternative:\n")
                for item in low_confidence:
                    print(f"\nLocal: {item['local']['artist']} - {item['local']['title']}")
                    print(f"Match: {item['soundcloud']['artist']} - {item['soundcloud']['title']} [{item['confidence']:.2f}]")

                    if item['candidates']:
                        for j, c in enumerate(item['candidates'][:5]):
                            marker = "→" if j == 0 else " "
                            print(f"  {marker} {j+1}. [{c['score']:.2f}] {c['track']['artist']} - {c['track']['title']}")

                    choice = input("Accept? (y/n/1-5): ").strip().lower()
                    if choice == 'y':
                        all_matched_ids.append(item['soundcloud']['soundcloud_id'])
                        print("  Added!")
                    elif choice.isdigit() and 1 <= int(choice) <= len(item['candidates']):
                        idx = int(choice) - 1
                        selected = item['candidates'][idx]['track']
                        all_matched_ids.append(selected['soundcloud_id'])
                        print(f"  Added: {selected['title']}")
        except EOFError:
            print("\n(Skipping interactive mode)")

    print(f"\n\nFinal count: {len(all_matched_ids)} tracks ready for SoundCloud playlist")

    # Save final list
    with open("final_sc_ids.txt", "w") as f:
        for sc_id in all_matched_ids:
            f.write(f"{sc_id}\n")
    print("Saved to: final_sc_ids.txt")


if __name__ == "__main__":
    main()
