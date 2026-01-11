#!/usr/bin/env python3
"""
Script to match NYE25 playlist tracks to SoundCloud with detailed output.
"""

import time
from pathlib import Path

from music_minion.core.database import get_db_connection
from music_minion.domain.library import providers
from music_minion.domain.library.provider import ProviderConfig
from music_minion.domain.playlists import crud
from music_minion.domain.playlists.matching import (
    batch_score_candidates,
    generate_search_queries,
)


def get_playlist_tracks(playlist_name: str) -> list[dict]:
    """Get tracks from a local playlist."""
    playlist = crud.get_playlist_by_name(playlist_name)
    if not playlist:
        raise ValueError(f"Playlist '{playlist_name}' not found")
    return crud.get_playlist_tracks(playlist["id"])


def match_track_to_soundcloud(
    track: dict,
    soundcloud_state,
    soundcloud_provider,
    verbose: bool = True,
) -> tuple[any, dict | None, float, list[dict]]:
    """
    Match a single track to SoundCloud.

    Returns: (updated_state, best_match, confidence, all_candidates)
    """
    title = track.get("title", "Unknown")
    artist = track.get("artist", "Unknown")
    top_level_artist = track.get("top_level_artist") or artist
    duration = track.get("duration", 0)

    # Generate search queries
    search_queries = generate_search_queries({
        "title": title,
        "artist": artist,
        "top_level_artist": top_level_artist,
    })

    if verbose:
        print(f"\n{'='*60}")
        print(f"Track: {artist} - {title}")
        print(f"Duration: {duration}s")
        print(f"Search queries: {search_queries[:3]}")

    # Search SoundCloud with multiple queries
    all_results: dict[str, dict] = {}

    for query in search_queries[:3]:
        soundcloud_state, sc_results = soundcloud_provider.search(soundcloud_state, query)

        if verbose:
            print(f"  Query '{query}': {len(sc_results)} results")

        for sc_id, meta in sc_results:
            if sc_id not in all_results:
                all_results[sc_id] = meta

        time.sleep(0.1)  # Rate limiting

    if verbose:
        print(f"Total unique results: {len(all_results)}")

    if not all_results:
        return soundcloud_state, None, 0.0, []

    # Score all candidates
    candidates_list = list(all_results.items())
    scored_candidates = batch_score_candidates(
        {
            "title": title,
            "artist": artist,
            "top_level_artist": top_level_artist,
            "duration_ms": int(duration * 1000),
        },
        candidates_list,
    )

    if verbose and scored_candidates:
        print(f"\nTop 5 matches:")
        for i, cand in enumerate(scored_candidates[:5]):
            print(f"  {i+1}. [{cand.confidence_score:.2f}] {cand.soundcloud_artist} - {cand.soundcloud_title}")
            print(f"      ID: {cand.soundcloud_id}")

    if scored_candidates:
        best = scored_candidates[0]
        return soundcloud_state, {
            "id": best.soundcloud_id,
            "title": best.soundcloud_title,
            "artist": best.soundcloud_artist,
            "confidence": best.confidence_score,
        }, best.confidence_score, scored_candidates

    return soundcloud_state, None, 0.0, []


def main():
    playlist_name = "NYE25"
    min_confidence = 0.60  # Default threshold

    print(f"Loading playlist: {playlist_name}")
    tracks = get_playlist_tracks(playlist_name)
    print(f"Found {len(tracks)} tracks")

    # Initialize SoundCloud
    print("\nInitializing SoundCloud...")
    soundcloud = providers.get_provider("soundcloud")
    soundcloud_state = soundcloud.init_provider(
        ProviderConfig(name="soundcloud", enabled=True)
    )

    if not soundcloud_state.authenticated:
        print("❌ SoundCloud not authenticated!")
        return

    print("✅ SoundCloud authenticated")

    # Match each track
    matched = []
    unmatched = []
    low_confidence = []

    for i, track in enumerate(tracks):
        print(f"\n[{i+1}/{len(tracks)}]", end="")

        soundcloud_state, best_match, confidence, candidates = match_track_to_soundcloud(
            track, soundcloud_state, soundcloud, verbose=True
        )

        if best_match and confidence >= min_confidence:
            matched.append({
                "track": track,
                "match": best_match,
                "confidence": confidence,
            })
            print(f"✅ MATCHED (confidence: {confidence:.2f})")
        elif best_match and confidence < min_confidence:
            low_confidence.append({
                "track": track,
                "match": best_match,
                "confidence": confidence,
                "candidates": candidates,
            })
            print(f"⚠️  LOW CONFIDENCE (confidence: {confidence:.2f})")
        else:
            unmatched.append(track)
            print(f"❌ NO MATCH FOUND")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total tracks: {len(tracks)}")
    print(f"Matched (>={min_confidence}): {len(matched)}")
    print(f"Low confidence (<{min_confidence}): {len(low_confidence)}")
    print(f"No match: {len(unmatched)}")

    if low_confidence:
        print(f"\n--- Low Confidence Matches (review these) ---")
        for item in low_confidence:
            t = item["track"]
            m = item["match"]
            print(f"\n  Local: {t.get('artist')} - {t.get('title')}")
            print(f"  SC:    {m['artist']} - {m['title']}")
            print(f"  Confidence: {item['confidence']:.2f}")
            print(f"  SC ID: {m['id']}")

    if unmatched:
        print(f"\n--- Unmatched Tracks ---")
        for t in unmatched:
            print(f"  • {t.get('artist')} - {t.get('title')}")

    # Save results
    print("\n\nSaving matched track IDs to matched_soundcloud_ids.txt...")
    with open("matched_soundcloud_ids.txt", "w") as f:
        f.write("# Matched SoundCloud track IDs for NYE25\n")
        f.write(f"# Total: {len(matched)} matched, {len(low_confidence)} low confidence\n\n")

        f.write("# High confidence matches:\n")
        for item in matched:
            f.write(f"{item['match']['id']}\n")

        if low_confidence:
            f.write("\n# Low confidence matches (uncomment to include):\n")
            for item in low_confidence:
                f.write(f"# {item['match']['id']}  # {item['confidence']:.2f} - {item['track'].get('title')}\n")

    print("Done!")


if __name__ == "__main__":
    main()
