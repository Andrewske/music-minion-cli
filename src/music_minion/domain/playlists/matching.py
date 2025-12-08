"""
Optimized track matching for Spotify → SoundCloud playlist conversion.

Uses batch processing and early filtering for 8-24x performance improvement
over naive per-comparison approach.

Performance characteristics (50 tracks):
- Notebook approach: ~120 seconds
- Optimized approach: ~5-15 seconds
"""

import re
from typing import Any, NamedTuple

import numpy as np
from rapidfuzz import distance, fuzz, process
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ...domain.library.deduplication import normalize_string


class MatchCandidate(NamedTuple):
    """Scored match candidate for a Spotify track."""

    soundcloud_id: str
    soundcloud_title: str
    soundcloud_artist: str
    soundcloud_duration: float
    title_similarity: float
    artist_similarity: float
    duration_match: float
    confidence_score: float


# Ensemble scoring weights (tuned from notebook experiments)
ENSEMBLE_WEIGHTS = {
    "title": 0.65,  # Most reliable indicator
    "artist": 0.25,  # Often has extra collaborators
    "duration": 0.10,  # Reduced due to false positives
}

MIN_CONFIDENCE_THRESHOLD = 0.60


def generate_search_queries(spotify_track: dict[str, Any]) -> list[str]:
    """Generate multiple search query variants for better SoundCloud matching.

    Args:
        spotify_track: Dict with 'title', 'artist', 'top_level_artist' keys

    Returns:
        List of query strings to try (most promising first)
    """
    title = spotify_track["title"]
    artist = spotify_track.get("top_level_artist") or spotify_track["artist"]

    # Clean title: remove featuring/remix noise for fallback queries
    clean_title = re.sub(
        r"\s*[\(\[]?(feat\.?|ft\.?|featuring)[^\)\]]*[\)\]]?", "", title, flags=re.I
    )
    clean_title = re.sub(
        r"\s*[\(\[]?(remix|vip|extended|edit)[^\)\]]*[\)\]]?",
        "",
        clean_title,
        flags=re.I,
    )
    clean_title = clean_title.strip()

    variants = [
        f"{title} - {artist}",  # Primary: Standard format
        f"{title} {artist}",  # No separator (common on SC)
        f"{artist} {title}",  # Artist first
        title,  # Title only (fallback)
    ]

    # Add clean title variant if different
    if clean_title and clean_title != title:
        variants.append(f"{clean_title} {artist}")

    return variants[:4]  # Limit to 4 queries max


def quick_filter_candidates(
    query_normalized: str, candidates: list[tuple[str, str]], top_n: int = 10
) -> list[int]:
    """Fast pre-filter using Jaccard similarity on tokens.

    Reduces expensive ensemble scoring from ~50 candidates to ~10.

    Args:
        query_normalized: Normalized query string
        candidates: List of (candidate_id, normalized_candidate_text) tuples
        top_n: Number of top candidates to return

    Returns:
        List of candidate indices sorted by score (best first)
    """
    if not candidates:
        return []

    query_tokens = set(query_normalized.split())
    if not query_tokens:
        return list(range(min(top_n, len(candidates))))

    scores = []
    for idx, (_, candidate_text) in enumerate(candidates):
        candidate_tokens = set(candidate_text.split())
        if not candidate_tokens:
            scores.append((idx, 0.0))
            continue

        intersection = query_tokens & candidate_tokens
        union = query_tokens | candidate_tokens
        jaccard = len(intersection) / len(union) if union else 0.0
        scores.append((idx, jaccard))

    # Sort by score and return top N indices
    sorted_scores = sorted(scores, key=lambda x: x[1], reverse=True)
    return [idx for idx, _ in sorted_scores[:top_n]]


def batch_tfidf_similarity(query_text: str, candidate_texts: list[str]) -> np.ndarray:
    """Compute TF-IDF cosine similarity for query vs all candidates.

    Optimization: Fits vectorizer ONCE instead of per-comparison.

    Args:
        query_text: Normalized query string
        candidate_texts: List of normalized candidate strings

    Returns:
        1D array of similarity scores (0.0-1.0) for each candidate
    """
    if not candidate_texts:
        return np.array([])

    all_texts = [query_text] + candidate_texts

    try:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), lowercase=True)
        vectors = vectorizer.fit_transform(all_texts)
        similarities = cosine_similarity(vectors[0:1], vectors[1:])[0]
        return similarities
    except (ValueError, IndexError):
        # Empty vocabulary or other error
        return np.zeros(len(candidate_texts))


def batch_fuzzy_similarity(query_text: str, candidate_texts: list[str]) -> np.ndarray:
    """Compute RapidFuzz token_set_ratio for query vs all candidates.

    Optimization: Uses cdist for batch processing instead of individual calls.

    Args:
        query_text: Normalized query string
        candidate_texts: List of normalized candidate strings

    Returns:
        1D array of similarity scores (0.0-1.0) for each candidate
    """
    if not candidate_texts:
        return np.array([])

    scores = process.cdist([query_text], candidate_texts, scorer=fuzz.token_set_ratio)[
        0
    ]
    return scores / 100.0  # Normalize to 0.0-1.0


def batch_jaro_similarity(query_text: str, candidate_texts: list[str]) -> np.ndarray:
    """Compute Jaro-Winkler similarity for query vs all candidates.

    Args:
        query_text: Normalized query string
        candidate_texts: List of normalized candidate strings

    Returns:
        1D array of similarity scores (0.0-1.0) for each candidate
    """
    if not candidate_texts:
        return np.array([])

    scores = [
        distance.JaroWinkler.similarity(query_text, cand) for cand in candidate_texts
    ]
    return np.array(scores)


def calculate_substring_penalty(norm_query: str, norm_candidate: str) -> float:
    """Calculate penalty for substring matches to avoid false positives.

    Prevents: "By Your Side" matching "Wake Up By Your Side"
    Allows: "Selector 2025 Remake" matching "Selector (2025 Remake)"

    Args:
        norm_query: Normalized query string
        norm_candidate: Normalized candidate string

    Returns:
        Penalty score (0.0 = reject, 1.0 = no penalty)
    """
    if norm_query == norm_candidate:
        return 1.0

    # Check if query is substring of candidate
    if norm_query in norm_candidate:
        position = norm_candidate.index(norm_query)
        length_ratio = len(norm_query) / len(norm_candidate)

        # Reject if query is small portion OR not at start
        if length_ratio < 0.7 or position > 0:
            return 0.0
        return 0.85 * length_ratio

    # Check if candidate is substring of query
    if norm_candidate in norm_query:
        position = norm_query.index(norm_candidate)
        length_ratio = len(norm_candidate) / len(norm_query)

        if length_ratio < 0.7 or position > 0:
            return 0.0
        return 0.85 * length_ratio

    return 1.0  # Not a substring - no penalty


def calculate_token_subset_penalty(norm_query: str, norm_candidate: str) -> float:
    """Calculate penalty when query tokens are small subset of candidate.

    Prevents: "with your love" matching "marmalade for your love with tommy villiers"

    Args:
        norm_query: Normalized query string
        norm_candidate: Normalized candidate string

    Returns:
        Penalty score (0.2-1.0, lower = worse match)
    """
    if not norm_query or not norm_candidate:
        return 0.0

    tokens_query = set(norm_query.split())
    tokens_candidate = set(norm_candidate.split())

    if not tokens_query or not tokens_candidate:
        return 0.0

    intersection = tokens_query & tokens_candidate
    union = tokens_query | tokens_candidate

    overlap_ratio_query = len(intersection) / len(tokens_query)
    overlap_ratio_candidate = len(intersection) / len(tokens_candidate)
    jaccard = len(intersection) / len(union)

    # Query fully contained but small part of candidate
    if overlap_ratio_query >= 0.9 and overlap_ratio_candidate < 0.5:
        return 0.2  # Heavy penalty

    # Only some tokens match and scattered
    if jaccard < 0.4:
        return 0.5

    # Most tokens match on both sides
    if overlap_ratio_query >= 0.8 and overlap_ratio_candidate >= 0.6:
        return 1.0

    return 0.5 + (jaccard * 0.5)


def calculate_duration_score(
    spotify_duration_ms: float, soundcloud_duration_s: float, track_title: str
) -> float:
    """Calculate adaptive duration match score based on track type.

    Different tolerances for extended/remix/original versions.

    Args:
        spotify_duration_ms: Spotify duration in milliseconds
        soundcloud_duration_s: SoundCloud duration in seconds
        track_title: Combined title for detecting track type

    Returns:
        Duration match score (0.0-1.0)
    """
    spotify_s = spotify_duration_ms / 1000.0
    diff = abs(spotify_s - soundcloud_duration_s)

    title_lower = track_title.lower()
    is_extended = "extended" in title_lower or "ext" in title_lower
    is_remix = "remix" in title_lower or "rework" in title_lower
    is_vip = "vip" in title_lower
    is_edit = "edit" in title_lower or "radio edit" in title_lower

    if is_extended:
        return 1.0 if diff <= 30 else (0.7 if diff <= 60 else 0.3)
    elif is_remix or is_vip:
        return 1.0 if diff <= 10 else (0.6 if diff <= 20 else 0.2)
    elif is_edit:
        return 1.0 if diff <= 5 else (0.7 if diff <= 15 else 0.3)
    else:
        return (
            1.0 if diff <= 1 else (0.7 if diff <= 3 else (0.4 if diff <= 10 else 0.0))
        )


def batch_score_candidates(
    spotify_track: dict[str, Any],
    soundcloud_candidates: list[tuple[str, dict[str, Any]]],
) -> list[MatchCandidate]:
    """Score all SoundCloud candidates for a Spotify track using batch processing.

    Optimizations:
    1. Quick pre-filter to top 10 candidates (Jaccard)
    2. Batch TF-IDF scoring (one vectorizer fit)
    3. Batch RapidFuzz scoring (cdist)
    4. Ensemble combination with penalties

    Args:
        spotify_track: Dict with 'title', 'artist', 'duration_ms', 'top_level_artist'
        soundcloud_candidates: List of (track_id, metadata) tuples

    Returns:
        List of MatchCandidate objects sorted by confidence (best first)
    """
    if not soundcloud_candidates:
        return []

    # Normalize Spotify track info
    sp_title = spotify_track["title"]
    sp_artist = spotify_track.get("top_level_artist") or spotify_track["artist"]
    sp_duration_ms = spotify_track.get("duration_ms", 0)

    sp_title_norm = normalize_string(sp_title)
    sp_artist_norm = normalize_string(sp_artist)
    sp_combined_norm = normalize_string(f"{sp_title} {sp_artist}")

    # Normalize all candidates
    candidates_normalized = []
    for sc_id, meta in soundcloud_candidates:
        sc_title = meta["title"]
        sc_artist = meta["artist"]
        sc_title_norm = normalize_string(sc_title)
        sc_artist_norm = normalize_string(sc_artist)
        sc_combined_norm = normalize_string(f"{sc_artist} {sc_title}")

        candidates_normalized.append(
            (sc_id, meta, sc_title_norm, sc_artist_norm, sc_combined_norm)
        )

    # Step 1: Quick pre-filter to top 10 using Jaccard
    candidate_texts = [cand[4] for cand in candidates_normalized]  # combined_norm
    top_indices = quick_filter_candidates(
        sp_combined_norm,
        [(cand[0], cand[4]) for cand in candidates_normalized],
        top_n=min(10, len(candidates_normalized)),
    )

    if not top_indices:
        return []

    # Filter to top candidates
    top_candidates = [candidates_normalized[idx] for idx in top_indices]

    # Step 2: Batch TF-IDF scoring on titles
    top_title_texts = [cand[4] for cand in top_candidates]  # combined_norm
    tfidf_scores = batch_tfidf_similarity(sp_combined_norm, top_title_texts)

    # Step 3: Batch RapidFuzz scoring on artists
    top_artist_texts = [cand[3] for cand in top_candidates]  # artist_norm
    fuzzy_scores = batch_fuzzy_similarity(sp_artist_norm, top_artist_texts)

    # Step 4: Batch Jaro-Winkler on titles
    jaro_scores = batch_jaro_similarity(sp_combined_norm, top_title_texts)

    # Step 5: Build MatchCandidate objects with ensemble scoring
    results = []
    for idx, (
        sc_id,
        meta,
        sc_title_norm,
        sc_artist_norm,
        sc_combined_norm,
    ) in enumerate(top_candidates):
        # Individual metric scores
        title_tfidf = tfidf_scores[idx]
        artist_fuzzy = fuzzy_scores[idx]
        title_jaro = jaro_scores[idx]

        # Penalties
        substring_penalty = calculate_substring_penalty(
            sp_combined_norm, sc_combined_norm
        )
        token_penalty = calculate_token_subset_penalty(
            sp_combined_norm, sc_combined_norm
        )

        # Ensemble title similarity
        title_sim = (
            title_tfidf * 0.25
            + artist_fuzzy * 0.20
            + title_jaro * 0.15
            + substring_penalty * 0.20
            + token_penalty * 0.20
        )

        # Artist similarity (lenient fuzzy matching)
        artist_sim = artist_fuzzy

        # Duration match
        sc_duration = meta.get("duration", 0)
        duration_score = calculate_duration_score(
            sp_duration_ms, sc_duration, f"{sp_title} {meta['title']}"
        )

        # Weighted confidence score
        confidence = (
            title_sim * ENSEMBLE_WEIGHTS["title"]
            + artist_sim * ENSEMBLE_WEIGHTS["artist"]
            + duration_score * ENSEMBLE_WEIGHTS["duration"]
        )

        # Apply penalties for low title/artist similarity
        if title_sim < 0.70:
            confidence *= 0.6
        if title_sim < 0.65 and artist_sim < 0.65:
            confidence *= 0.5

        results.append(
            MatchCandidate(
                soundcloud_id=str(sc_id),
                soundcloud_title=meta["title"],
                soundcloud_artist=meta["artist"],
                soundcloud_duration=sc_duration,
                title_similarity=title_sim,
                artist_similarity=artist_sim,
                duration_match=duration_score,
                confidence_score=confidence,
            )
        )

    # Sort by confidence and filter by threshold
    results.sort(key=lambda x: x.confidence_score, reverse=True)
    return [r for r in results if r.confidence_score >= MIN_CONFIDENCE_THRESHOLD]
