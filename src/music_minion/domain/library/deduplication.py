"""
Track matching system for multi-source library.

Matches tracks across providers (e.g., SoundCloud track = local file)
using TF-IDF text search for fast, accurate matching.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ...core import database


def normalize_string(s: Optional[str]) -> str:
    """Normalize string for comparison.

    Removes punctuation, extra whitespace, converts to lowercase.

    Args:
        s: String to normalize

    Returns:
        Normalized string

    Examples:
        >>> normalize_string("Artist - Song (Remix)")
        'artist song remix'
        >>> normalize_string("The Beatles")
        'beatles'
    """
    if not s:
        return ""

    # Convert to lowercase
    s = s.lower()

    # Remove common prefixes
    s = re.sub(r"^(the|a|an)\s+", "", s)

    # Remove everything except alphanumeric and spaces
    s = re.sub(r"[^\w\s]", "", s)

    # Collapse multiple spaces
    s = re.sub(r"\s+", " ", s)

    return s.strip()


def find_best_matches_tfidf(
    sc_tracks: List[Tuple[str, Dict[str, Any]]],
    local_tracks: List[Dict[str, Any]],
    min_score: float = 0.7,
) -> List[Tuple[str, Optional[Dict[str, Any]], float]]:
    """Batch match SoundCloud tracks to local tracks using TF-IDF search.

    This is MUCH faster than brute-force comparison for large track libraries.
    Builds a TF-IDF index once, then performs fast lookups for each SC track.

    Args:
        sc_tracks: List of (track_id, metadata) tuples from SoundCloud
        local_tracks: List of existing track dictionaries
        min_score: Minimum cosine similarity score (0.0-1.0)

    Returns:
        List of (sc_track_id, best_match_dict, confidence_score) tuples

    Performance:
        - Pre-processing: ~1 second (one-time cost)
        - Per-track lookup: ~10ms
        - Total for 200 tracks: ~3 seconds (vs 30-60s brute force)

    Examples:
        >>> results = find_best_matches_tfidf(sc_tracks, local_tracks)
        >>> for sc_id, match, score in results:
        ...     if score >= 0.8:
        ...         print(f"High confidence: {sc_id} -> {match['id']} ({score:.3f})")
    """
    if not local_tracks or not sc_tracks:
        return [(sc_id, None, 0.0) for sc_id, _ in sc_tracks]

    # Build combined strings for local tracks
    # Include filename for better matching (filenames often match SC format better)
    local_strings = []
    for track in local_tracks:
        artist = track.get("artist", "") or ""
        title = track.get("title", "") or ""

        # Extract filename (without extension or path) from path
        filepath = track.get("local_path", "")
        if filepath:
            filename = Path(filepath).stem
        else:
            filename = ""

        # Combine artist, title, and filename for matching
        # Filename often has "{artist} - {title}" format
        combined = normalize_string(f"{artist} {title} {filename}")
        local_strings.append(combined)

    # Build TF-IDF index (one-time cost)
    vectorizer = TfidfVectorizer(
        min_df=1,
        ngram_range=(1, 2),  # Unigrams and bigrams
        lowercase=True,
        analyzer="word",
    )

    try:
        local_vectors = vectorizer.fit_transform(local_strings)
    except ValueError:
        # Empty vocabulary (shouldn't happen with real data)
        return [(sc_id, None, 0.0) for sc_id, _ in sc_tracks]

    # Match each SC track
    results = []

    for sc_id, sc_metadata in sc_tracks:
        # Build combined string for SC track
        sc_artist = sc_metadata.get("artist", "") or ""
        sc_title = sc_metadata.get("title", "") or ""
        sc_combined = normalize_string(f"{sc_artist} {sc_title}")

        try:
            # Vectorize SC track
            sc_vector = vectorizer.transform([sc_combined])

            # Compute cosine similarity against all locals
            similarities = cosine_similarity(sc_vector, local_vectors)[0]

            # Find best match
            best_idx = np.argmax(similarities)
            best_score = float(similarities[best_idx])

            if best_score >= min_score:
                best_match = local_tracks[best_idx]
                results.append((sc_id, best_match, best_score))
            else:
                results.append((sc_id, None, best_score))

        except Exception:
            # Fallback if vectorization fails
            results.append((sc_id, None, 0.0))

    return results


def apply_manual_corrections(
    matches: List[Dict[str, Any]], corrections_file: str
) -> List[Dict[str, Any]]:
    """Apply manual corrections from CSV file to matching results.

    Allows manual override of incorrect matches by looking up correct
    track IDs and filling them in a corrections CSV file.

    Args:
        matches: List of match dicts with 'sc_id' and 'local_id'
        corrections_file: Path to CSV with corrections
            Required columns: sc_id, correct_id
            If correct_id is filled, it replaces local_id

    Returns:
        Updated matches list with corrections applied

    CSV Format:
        sc_id,sc_title,sc_artist,local_id,local_title,local_artist,score,correct_id,notes
        2167517061,Song,Artist,2862,Wrong Song,Artist,0.725,5896,Title didn't match
        2192068631,Other,Artist,2259,Bad Match,Artist,0.746,None,No valid match exists

    Correct ID Values:
        - Leave blank: No correction needed (match is correct)
        - Track ID (e.g., 5896): Replace with this track
        - "None": Mark as invalid match (no correct track exists)

    Example:
        >>> matches = find_best_matches_tfidf(sc_tracks, local_tracks)
        >>> # ... export to CSV, manually fill correct_id for wrong matches ...
        >>> corrected = apply_manual_corrections(matches, 'corrections.csv')
    """
    corrections_path = Path(corrections_file)

    if not corrections_path.exists():
        print(f"⚠️  Corrections file not found: {corrections_file}")
        print("Returning original matches unchanged")
        return matches

    # Load corrections
    try:
        corrections_df = pd.read_csv(corrections_file)
    except Exception as e:
        print(f"❌ Error reading corrections file: {e}")
        return matches

    # Build correction map: sc_id -> correct_id or None
    correction_map = {}
    corrections_applied = 0

    for _, row in corrections_df.iterrows():
        sc_id = str(row["sc_id"])
        correct_id = row.get("correct_id", "")

        # Only apply if correct_id is filled in
        if correct_id and str(correct_id).strip():
            correct_id_str = str(correct_id).strip()

            # Check if user marked as "None" (no valid match exists)
            if correct_id_str.lower() == "none":
                correction_map[sc_id] = None  # Mark as no-match
                corrections_applied += 1
            else:
                # Valid track ID
                try:
                    correction_map[sc_id] = int(correct_id_str)
                    corrections_applied += 1
                except ValueError:
                    print(
                        f"⚠️  Warning: Invalid correct_id '{correct_id_str}' for sc_id {sc_id} (not a number or 'None')"
                    )

    if not correction_map:
        print("ℹ️  No corrections found in CSV (correct_id column empty)")
        return matches

    # Apply corrections
    corrected_matches = []

    # Get all tracks for lookup
    all_tracks = database.get_all_tracks()
    tracks_by_id = {t["id"]: t for t in all_tracks}

    for match in matches:
        sc_id = match["sc_id"]

        if sc_id in correction_map:
            # Apply correction
            correct_id = correction_map[sc_id]

            if correct_id is None:
                # User marked as "None" - this is an incorrect match with no valid alternative
                # Remove from matches (don't add to corrected_matches)
                continue
            elif correct_id in tracks_by_id:
                corrected_track = tracks_by_id[correct_id]
                corrected_match = match.copy()
                corrected_match["local_id"] = correct_id
                corrected_match["local_title"] = corrected_track.get("title")
                corrected_match["local_artist"] = corrected_track.get("artist")
                corrected_match["corrected"] = True  # Mark as corrected
                corrected_matches.append(corrected_match)
            else:
                print(
                    f"⚠️  Warning: correct_id {correct_id} not found for sc_id {sc_id}"
                )
                corrected_matches.append(match)
        else:
            # No correction needed
            corrected_matches.append(match)

    print(f"✓ Applied {corrections_applied} manual corrections from {corrections_file}")

    return corrected_matches
