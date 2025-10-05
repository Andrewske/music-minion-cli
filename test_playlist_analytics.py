#!/usr/bin/env python3
"""
Test script for playlist analytics functionality.

Tests all analytics functions:
1. get_basic_stats() - Basic playlist statistics
2. get_artist_analysis() - Artist distribution and diversity
3. get_genre_distribution() - Genre breakdown with percentages
4. get_tag_analysis() - Tag analysis by source
5. get_bpm_analysis() - BPM range and distribution
6. get_key_distribution() - Key distribution and harmonic pairs
7. get_year_distribution() - Year/era distribution
8. get_rating_analysis() - Rating counts and loved tracks
9. get_quality_metrics() - Completeness score
10. get_playlist_analytics() - Orchestrator function

Run with: uv run python test_playlist_analytics.py
"""

import os
import sys
import tempfile
import sqlite3
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from music_minion.core import database as db_module
from music_minion.domain.playlists import crud, analytics


def setup_test_database():
    """Create temporary test database with sample data."""
    # Create temporary database file
    temp_dir = tempfile.mkdtemp(prefix="mm_analytics_test_")
    test_db_path = Path(temp_dir) / "test.db"

    # Monkey-patch the get_database_path function to use our test database
    original_get_db_path = db_module.get_database_path
    db_module.get_database_path = lambda: test_db_path

    # Initialize schema
    db_module.init_database()

    # Get connection to our test database directly
    conn = sqlite3.connect(str(test_db_path))
    conn.row_factory = sqlite3.Row

    # Add sample tracks
    tracks_data = [
        # (file_path, title, artist, album, genre, year, duration, key, bpm)
        ('/music/track1.mp3', 'Track 1', 'Artist A', 'Album 1', 'Dubstep', 2023, 240, 'A minor', 140),
        ('/music/track2.mp3', 'Track 2', 'Artist A', 'Album 1', 'Dubstep', 2023, 230, 'C major', 145),
        ('/music/track3.mp3', 'Track 3', 'Artist B', 'Album 2', 'Drum & Bass', 2024, 250, 'G major', 174),
        ('/music/track4.mp3', 'Track 4', 'Artist C', 'Album 3', 'Dubstep', 2022, 260, 'A minor', 142),
        ('/music/track5.mp3', 'Track 5', 'Artist A', 'Album 1', 'Bass House', 2025, 220, 'F major', 128),
        ('/music/track6.mp3', 'Track 6', 'Artist D', 'Album 4', 'Drum & Bass', 2024, 245, 'D major', 170),
        ('/music/track7.mp3', 'Track 7', 'Artist B', 'Album 2', 'Dubstep', 2023, 235, 'E minor', 150),
        ('/music/track8.mp3', 'Track 8', 'Artist E', 'Album 5', None, None, 210, None, None),  # Missing metadata
    ]

    track_ids = []
    for track_data in tracks_data:
        cursor = conn.execute("""
            INSERT INTO tracks (file_path, title, artist, album, genre, year, duration, key_signature, bpm)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, track_data)
        track_ids.append(cursor.lastrowid)

    # Create a manual playlist with first 5 tracks
    cursor = conn.execute("""
        INSERT INTO playlists (name, type, description)
        VALUES (?, ?, ?)
    """, ('Test Manual Playlist', 'manual', 'Test playlist for analytics'))
    manual_playlist_id = cursor.lastrowid

    # Add tracks to manual playlist
    for i, track_id in enumerate(track_ids[:5]):
        conn.execute("""
            INSERT INTO playlist_tracks (playlist_id, track_id, position)
            VALUES (?, ?, ?)
        """, (manual_playlist_id, track_id, i))

    # Add tags to tracks
    tags_data = [
        (track_ids[0], 'high-energy', 'ai', 0.92),
        (track_ids[0], 'heavy-bass', 'ai', 0.88),
        (track_ids[0], 'favorite', 'user', None),
        (track_ids[1], 'high-energy', 'ai', 0.85),
        (track_ids[1], 'melodic', 'ai', 0.78),
        (track_ids[2], 'fast-paced', 'ai', 0.90),
        (track_ids[3], 'heavy-bass', 'ai', 0.95),
        (track_ids[3], 'opener', 'user', None),
    ]

    for track_id, tag_name, source, confidence in tags_data:
        conn.execute("""
            INSERT INTO tags (track_id, tag_name, source, confidence)
            VALUES (?, ?, ?, ?)
        """, (track_id, tag_name, source, confidence))

    # Add ratings
    ratings_data = [
        (track_ids[0], 'love'),
        (track_ids[1], 'like'),
        (track_ids[2], 'love'),
        (track_ids[3], 'skip'),
    ]

    for track_id, rating_type in ratings_data:
        conn.execute("""
            INSERT INTO ratings (track_id, rating_type, hour_of_day, day_of_week)
            VALUES (?, ?, ?, ?)
        """, (track_id, rating_type, 14, 3))

    conn.commit()

    return conn, manual_playlist_id, track_ids, test_db_path, original_get_db_path


def test_basic_stats(playlist_id: int):
    """Test get_basic_stats() function."""
    print("\n=== Test 1: Basic Stats ===")

    stats = analytics.get_basic_stats(playlist_id)

    print(f"Total tracks: {stats['total_tracks']}")
    print(f"Total duration: {stats['total_duration']:.1f}s")
    print(f"Avg duration: {stats['avg_duration']:.1f}s")
    print(f"Year range: {stats['year_min']}-{stats['year_max']}")

    # Validate
    assert stats['total_tracks'] == 5, f"Expected 5 tracks, got {stats['total_tracks']}"
    assert stats['total_duration'] > 0, "Total duration should be > 0"
    assert stats['year_min'] == 2022, f"Expected min year 2022, got {stats['year_min']}"
    assert stats['year_max'] == 2025, f"Expected max year 2025, got {stats['year_max']}"

    print("✅ Basic stats test passed")


def test_artist_analysis(playlist_id: int):
    """Test get_artist_analysis() function."""
    print("\n=== Test 2: Artist Analysis ===")

    artists = analytics.get_artist_analysis(playlist_id, top_n=10)

    print(f"Top artists: {artists['top_artists']}")
    print(f"Total unique artists: {artists['total_unique_artists']}")
    print(f"Diversity ratio: {artists['diversity_ratio']:.2f}")

    # Validate
    assert len(artists['top_artists']) > 0, "Should have at least one artist"
    assert artists['total_unique_artists'] >= 1, "Should have at least 1 unique artist"
    assert artists['diversity_ratio'] > 0, "Diversity ratio should be > 0"

    # Artist A should be top with 3 tracks
    top_artist = artists['top_artists'][0]
    assert top_artist['artist'] == 'Artist A', f"Expected 'Artist A', got {top_artist['artist']}"
    assert top_artist['track_count'] == 3, f"Expected 3 tracks for Artist A, got {top_artist['track_count']}"

    print("✅ Artist analysis test passed")


def test_genre_distribution(playlist_id: int):
    """Test get_genre_distribution() function."""
    print("\n=== Test 3: Genre Distribution ===")

    genre_data = analytics.get_genre_distribution(playlist_id)
    genres = genre_data['genres']

    print(f"Genres: {genres}")

    # Validate
    assert len(genres) > 0, "Should have at least one genre"

    # Dubstep should be top with 3 tracks (60%)
    top_genre = genres[0]
    assert top_genre['genre'] == 'Dubstep', f"Expected 'Dubstep', got {top_genre['genre']}"
    assert top_genre['count'] == 3, f"Expected 3 tracks, got {top_genre['count']}"
    assert 55 <= top_genre['percentage'] <= 65, f"Expected ~60%, got {top_genre['percentage']:.1f}%"

    print("✅ Genre distribution test passed")


def test_tag_analysis(playlist_id: int):
    """Test get_tag_analysis() function."""
    print("\n=== Test 4: Tag Analysis ===")

    tags = analytics.get_tag_analysis(playlist_id, top_n=10)

    print(f"Top AI tags: {tags['top_ai_tags']}")
    print(f"Top user tags: {tags['top_user_tags']}")
    print(f"Most confident AI tags: {tags['most_confident_ai_tags']}")

    # Validate
    assert len(tags['top_ai_tags']) > 0, "Should have AI tags"
    assert len(tags['top_user_tags']) > 0, "Should have user tags"

    # high-energy should be in top AI tags (appears 2 times)
    ai_tag_names = [tag['tag_name'] for tag in tags['top_ai_tags']]
    assert 'high-energy' in ai_tag_names, "high-energy should be in top AI tags"

    print("✅ Tag analysis test passed")


def test_bpm_analysis(playlist_id: int):
    """Test get_bpm_analysis() function."""
    print("\n=== Test 5: BPM Analysis ===")

    bpm = analytics.get_bpm_analysis(playlist_id)

    print(f"BPM range: {bpm['min']:.0f}-{bpm['max']:.0f}")
    print(f"Average: {bpm['avg']:.0f}, Median: {bpm['median']:.0f}")
    print(f"Distribution: {bpm['distribution']}")

    # Validate
    assert bpm['min'] is not None, "Min BPM should not be None"
    assert bpm['max'] is not None, "Max BPM should not be None"
    assert bpm['min'] <= bpm['max'], "Min BPM should be <= Max BPM"
    assert bpm['avg'] > 0, "Average BPM should be > 0"

    # Check distribution sums to 5 tracks (all tracks in playlist have BPM data)
    total_in_dist = sum(bpm['distribution'].values())
    assert total_in_dist == 5, f"Expected 5 tracks with BPM data, got {total_in_dist}"

    print("✅ BPM analysis test passed")


def test_key_distribution(playlist_id: int):
    """Test get_key_distribution() function."""
    print("\n=== Test 6: Key Distribution ===")

    keys = analytics.get_key_distribution(playlist_id)

    print(f"Top keys: {keys['top_keys']}")
    print(f"Total unique keys: {keys['total_unique_keys']}")
    print(f"Harmonic pairs: {keys['harmonic_pairs_count']}")

    # Validate
    assert len(keys['top_keys']) > 0, "Should have at least one key"
    assert keys['total_unique_keys'] >= 1, "Should have at least 1 unique key"

    # A minor should be top with 2 tracks
    top_key = keys['top_keys'][0]
    assert top_key['key_signature'] == 'A minor', f"Expected 'A minor', got {top_key['key_signature']}"

    print("✅ Key distribution test passed")


def test_year_distribution(playlist_id: int):
    """Test get_year_distribution() function."""
    print("\n=== Test 7: Year Distribution ===")

    years = analytics.get_year_distribution(playlist_id)

    print(f"Decade distribution: {years['decade_distribution']}")
    print(f"Recent (2020+): {years['recent_count']} ({years['recent_percentage']:.1f}%)")
    print(f"Classic: {years['classic_count']}")

    # Validate
    assert years['recent_count'] > 0, "Should have recent tracks (2020+)"
    assert years['decade_distribution']['20s+'] > 0, "Should have 2020+ tracks"

    # All 5 tracks are from 2022-2025, so all should be recent
    assert years['recent_count'] == 5, f"Expected 5 recent tracks, got {years['recent_count']}"
    assert years['classic_count'] == 0, f"Expected 0 classic tracks, got {years['classic_count']}"

    print("✅ Year distribution test passed")


def test_rating_analysis(playlist_id: int):
    """Test get_rating_analysis() function."""
    print("\n=== Test 8: Rating Analysis ===")

    ratings = analytics.get_rating_analysis(playlist_id)

    print(f"Rating counts: {ratings['rating_counts']}")
    print(f"Most loved tracks: {ratings['most_loved_tracks']}")

    # Validate
    assert 'love' in ratings['rating_counts'], "Should have 'love' ratings"
    assert ratings['rating_counts']['love'] == 2, f"Expected 2 'love' ratings, got {ratings['rating_counts']['love']}"
    assert len(ratings['most_loved_tracks']) == 2, f"Expected 2 loved tracks, got {len(ratings['most_loved_tracks'])}"

    print("✅ Rating analysis test passed")


def test_quality_metrics(playlist_id: int):
    """Test get_quality_metrics() function."""
    print("\n=== Test 9: Quality Metrics ===")

    quality = analytics.get_quality_metrics(playlist_id)

    print(f"Total tracks: {quality['total_tracks']}")
    print(f"Missing BPM: {quality['missing_bpm']}")
    print(f"Missing key: {quality['missing_key']}")
    print(f"Missing year: {quality['missing_year']}")
    print(f"Missing genre: {quality['missing_genre']}")
    print(f"Without tags: {quality['without_tags']}")
    print(f"Completeness score: {quality['completeness_score']:.1f}%")

    # Validate
    assert quality['total_tracks'] == 5, f"Expected 5 tracks, got {quality['total_tracks']}"
    assert quality['completeness_score'] >= 0 and quality['completeness_score'] <= 100, \
        f"Completeness score should be 0-100, got {quality['completeness_score']}"

    print("✅ Quality metrics test passed")


def test_playlist_analytics_orchestrator(playlist_id: int):
    """Test get_playlist_analytics() orchestrator function."""
    print("\n=== Test 10: Playlist Analytics Orchestrator ===")

    # Test full analytics
    analytics_full = analytics.get_playlist_analytics(playlist_id)

    print(f"Playlist name: {analytics_full['playlist_name']}")
    print(f"Playlist type: {analytics_full['playlist_type']}")
    print(f"Sections included: {list(analytics_full.keys())}")

    # Validate
    assert analytics_full['playlist_name'] == 'Test Manual Playlist', "Playlist name mismatch"
    assert analytics_full['playlist_type'] == 'manual', "Playlist type mismatch"
    assert 'basic' in analytics_full, "Should include basic stats"
    assert 'artists' in analytics_full, "Should include artist analysis"
    assert 'genres' in analytics_full, "Should include genre distribution"

    # Test section filtering
    analytics_bpm_only = analytics.get_playlist_analytics(playlist_id, sections=['bpm'])

    print(f"\nFiltered sections: {list(analytics_bpm_only.keys())}")

    assert 'bpm' in analytics_bpm_only, "Should include BPM section"
    assert 'artists' not in analytics_bpm_only, "Should NOT include artists section when filtered"

    print("✅ Playlist analytics orchestrator test passed")


def test_empty_playlist():
    """Test analytics with an empty playlist."""
    print("\n=== Test 11: Empty Playlist ===")

    # Create empty playlist
    with db_module.get_db_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO playlists (name, type)
            VALUES (?, ?)
        """, ('Empty Playlist', 'manual'))
        empty_playlist_id = cursor.lastrowid
        conn.commit()

    # Test basic stats with empty playlist
    stats = analytics.get_basic_stats(empty_playlist_id)

    print(f"Empty playlist stats: {stats}")

    # Validate
    assert stats['total_tracks'] == 0, "Empty playlist should have 0 tracks"
    assert stats['total_duration'] == 0, "Empty playlist should have 0 duration"

    print("✅ Empty playlist test passed")


def run_all_tests():
    """Run all analytics tests."""
    print("=" * 60)
    print("Playlist Analytics Test Suite")
    print("=" * 60)

    # Setup
    conn, manual_playlist_id, track_ids, test_db_path, original_get_db_path = setup_test_database()

    try:
        # Run tests
        test_basic_stats(manual_playlist_id)
        test_artist_analysis(manual_playlist_id)
        test_genre_distribution(manual_playlist_id)
        test_tag_analysis(manual_playlist_id)
        test_bpm_analysis(manual_playlist_id)
        test_key_distribution(manual_playlist_id)
        test_year_distribution(manual_playlist_id)
        test_rating_analysis(manual_playlist_id)
        test_quality_metrics(manual_playlist_id)
        test_playlist_analytics_orchestrator(manual_playlist_id)
        test_empty_playlist()

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()

        # Restore original function and clean up
        db_module.get_database_path = original_get_db_path
        if test_db_path.exists():
            test_db_path.unlink()
            test_db_path.parent.rmdir()


if __name__ == '__main__':
    run_all_tests()
