#!/usr/bin/env python3
"""One-time backfill script to match unlinked local tracks to SoundCloud tracks.

Algorithm: Merged v4 (v3 + EXP8 filename-as-ground-truth scoring).

Scoring thresholds:
  >=0.90 : auto-link  (UPDATE tracks SET soundcloud_id)
  0.50-0.89: candidate (INSERT INTO match_candidates)
  <0.50  : skip

Run with:
  uv run python scripts/backfill_sc_matches.py          # dry-run
  uv run python scripts/backfill_sc_matches.py --apply  # write to DB
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np
from loguru import logger
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from music_minion.core.database import get_db_connection

# ---------------------------------------------------------------------------
# Constants (v4)
# ---------------------------------------------------------------------------

NOISE_WORDS = {
    "free", "download", "dl", "out", "now", "official", "full", "stream",
    "original", "mix", "audio", "video", "premiere", "exclusive", "single",
    "master", "explicit", "ep", "vol",
}

ARTICLE_WORDS = {"the", "a", "an"}

REMIX_INDICATORS = {"remix", "flip", "vip", "edit", "rework", "bootleg"}
FEAT_INDICATORS = {"feat", "ft", "featuring"}

BRACKET_SUFFIX_RE = re.compile(
    r"\s*[\[\(](?:free\s*download|out\s*now|free\s*dl|free|dl|out|premiere|exclusive|official)[^\]\)]*[\]\)]",
    flags=re.IGNORECASE,
)

MONTH_PREFIX_RE = re.compile(
    r"^(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\s+\d{1,2}[_ ]",
    flags=re.IGNORECASE,
)
ISO_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\s+")
TRACK_NUM_PREFIX_RE = re.compile(r"^\d+\s*[-–._]\s*")
ALBUM_PREFIX_RE = re.compile(r"^[A-Za-z\s/\-]+_")

SYNONYM_MAP = {
    "ft": "feat",
    "featuring": "feat",
    "and": "&",
    "x": "&",
}


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_text(s: str | None) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^\w\s&#]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def normalize_for_substring(s: str | None) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^\w\s&#]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def clean_filename_stem(stem: str) -> str:
    for _ in range(3):
        new_stem = ALBUM_PREFIX_RE.sub("", stem)
        if new_stem == stem:
            break
        stem = new_stem
    stem = MONTH_PREFIX_RE.sub("", stem)
    stem = ISO_DATE_PREFIX_RE.sub("", stem)
    stem = TRACK_NUM_PREFIX_RE.sub("", stem)
    stem = re.sub(r"^\d{1,3}\s+", "", stem)
    stem = stem.replace("_", " ")
    return stem


def strip_bracket_suffixes(title: str) -> str:
    return BRACKET_SUFFIX_RE.sub("", title).strip()


def parse_sc_real_title(sc_title: str) -> str:
    cleaned = strip_bracket_suffixes(sc_title)
    if " - " in cleaned:
        return cleaned.split(" - ")[-1].strip()
    return cleaned


def normalize_synonyms(tokens: set[str]) -> set[str]:
    return {SYNONYM_MAP.get(tok, tok) for tok in tokens}


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

def tokenize(text: str) -> set[str]:
    normalized = normalize_text(text)
    normalized = normalized.replace("_", " ")
    tokens: set[str] = set()
    for tok in normalized.split():
        if tok.isdigit():
            continue
        if len(tok) < 2:
            continue
        if tok in NOISE_WORDS or tok in ARTICLE_WORDS:
            continue
        tokens.add(tok)
    return normalize_synonyms(tokens)


def get_critical_tokens(title: str, artist: str) -> set[str]:
    full_text = normalize_text(f"{title} {artist}")
    raw_tokens = full_text.split()
    critical: set[str] = set()
    normalized_raw = [SYNONYM_MAP.get(tok, tok) for tok in raw_tokens]
    i = 0
    while i < len(normalized_raw):
        tok = normalized_raw[i]
        if tok in REMIX_INDICATORS or tok in FEAT_INDICATORS:
            j = i + 1
            while j < len(normalized_raw) and normalized_raw[j] not in REMIX_INDICATORS and normalized_raw[j] not in FEAT_INDICATORS:
                candidate = normalized_raw[j]
                if not candidate.isdigit() and len(candidate) >= 2 and candidate not in NOISE_WORDS and candidate not in ARTICLE_WORDS:
                    critical.add(candidate)
                j += 1
            i = j
        else:
            i += 1
    return critical


def local_track_tokens(track: dict) -> tuple[set[str], set[str], set[str]]:
    """Returns (all_tokens, critical_tokens, artist_tokens)."""
    title = track.get("title") or ""
    artist = track.get("artist") or ""
    path = track.get("local_path", "")

    parts = []
    if title:
        parts.append(title)
    if artist:
        parts.append(artist)
    if path:
        stem = clean_filename_stem(Path(path).stem)
        parts.append(stem)

    all_tokens = tokenize(" ".join(parts))
    critical = get_critical_tokens(title, artist)
    artist_tokens = tokenize(artist) if artist else set()
    return all_tokens, critical, artist_tokens


def sc_track_tokens(track: dict) -> tuple[set[str], set[str], set[str]]:
    """Returns (all_tokens, real_title_tokens, sc_artist_tokens)."""
    title = track.get("title") or ""
    artist = track.get("artist") or ""

    full_tokens = tokenize(f"{title} {artist}")
    real_title = parse_sc_real_title(title)
    real_tokens = tokenize(f"{real_title} {artist}")
    sc_artist_tokens = tokenize(artist) if artist else set()

    combined = full_tokens | real_tokens
    return combined, real_tokens, sc_artist_tokens


def has_remix_indicators(tokens: set[str]) -> bool:
    non_vip_remix = REMIX_INDICATORS - {"vip"}
    return bool(tokens & non_vip_remix)


# ---------------------------------------------------------------------------
# TF-IDF index
# ---------------------------------------------------------------------------

def build_tfidf_index(sc_tracks: list[dict]) -> tuple[TfidfVectorizer, np.ndarray]:
    strings = []
    for t in sc_tracks:
        artist = t.get("artist", "") or ""
        title = t.get("title", "") or ""
        real_title = parse_sc_real_title(title)
        combined = normalize_text(f"{artist} {title} {real_title}")
        strings.append(combined)

    vectorizer = TfidfVectorizer(
        min_df=1, ngram_range=(1, 2), lowercase=True, analyzer="word",
    )
    matrix = vectorizer.fit_transform(strings)
    return vectorizer, matrix


def tfidf_top_k(
    local_track: dict,
    vectorizer: TfidfVectorizer,
    sc_matrix: np.ndarray,
    k: int = 10,
) -> list[tuple[int, float]]:
    title = local_track.get("title", "") or ""
    artist = local_track.get("artist", "") or ""
    path = local_track.get("local_path", "")
    filename = clean_filename_stem(Path(path).stem) if path else ""
    combined = normalize_text(f"{artist} {title} {filename}")

    try:
        vec = vectorizer.transform([combined])
    except Exception:
        return []

    sims = cosine_similarity(vec, sc_matrix)[0]
    top_indices = np.argsort(sims)[-k:][::-1]
    return [(int(idx), float(sims[idx])) for idx in top_indices if sims[idx] > 0]


# ---------------------------------------------------------------------------
# Artist-weighted containment scoring (v3/EXP3)
# ---------------------------------------------------------------------------

def containment_score_with_penalty(
    local_tokens: set[str],
    critical_tokens: set[str],
    sc_tokens: set[str],
    sc_real_tokens: set[str],
    local_artist_tokens: set[str],
    sc_artist_tokens: set[str],
) -> tuple[float, dict]:
    if not local_tokens:
        return 0.0, {
            "base": 0.0, "critical_penalty": 1.0, "noise_penalty": 1.0,
            "reverse_remix_penalty": 1.0, "artist_boost": 1.0,
            "intersection": set(), "used_sc_tokens": sc_tokens,
            "missing_critical": set(), "artist_matched": set(),
            "artist_missed": set(),
        }

    intersection_full = local_tokens & sc_tokens
    intersection_real = local_tokens & sc_real_tokens
    if len(intersection_real) >= len(intersection_full):
        intersection = intersection_real
        used_sc_tokens = sc_real_tokens
    else:
        intersection = intersection_full
        used_sc_tokens = sc_tokens

    non_artist_local = local_tokens - local_artist_tokens
    artist_matched = local_artist_tokens & used_sc_tokens
    artist_missed = local_artist_tokens - used_sc_tokens
    non_artist_matched = non_artist_local & used_sc_tokens

    weighted_num = len(artist_matched) * 2 + len(non_artist_matched)
    weighted_denom = len(local_artist_tokens) * 2 + len(non_artist_local)

    base = weighted_num / weighted_denom if weighted_denom > 0 else 0.0

    artist_boost = 1.0
    non_artist_coverage = len(non_artist_matched) / len(non_artist_local) if non_artist_local else 0.0
    if local_artist_tokens and local_artist_tokens.issubset(used_sc_tokens | sc_artist_tokens):
        if non_artist_coverage > 0.5:
            artist_boost = 1.1

    critical_penalty = 1.0
    actual_critical = critical_tokens - REMIX_INDICATORS - FEAT_INDICATORS
    missing_critical = set()
    if actual_critical:
        missing_critical = actual_critical - used_sc_tokens
        if missing_critical:
            critical_penalty = 0.5

    noise_penalty = 1.0
    if len(used_sc_tokens) > 2.5 * len(local_tokens):
        noise_penalty = 0.85

    reverse_remix_penalty = 1.0
    sc_has_remix = has_remix_indicators(used_sc_tokens) or has_remix_indicators(sc_tokens)
    local_has_remix = has_remix_indicators(local_tokens)
    if sc_has_remix and not local_has_remix:
        reverse_remix_penalty = 0.5

    raw_final = base * critical_penalty * noise_penalty * reverse_remix_penalty * artist_boost
    final = min(1.0, raw_final)

    debug = {
        "base": base,
        "critical_penalty": critical_penalty,
        "noise_penalty": noise_penalty,
        "reverse_remix_penalty": reverse_remix_penalty,
        "artist_boost": artist_boost,
        "non_artist_coverage": non_artist_coverage,
        "intersection": intersection,
        "used_sc_tokens": used_sc_tokens,
        "missing_critical": missing_critical,
        "artist_matched": artist_matched,
        "artist_missed": artist_missed,
    }
    return final, debug


# ---------------------------------------------------------------------------
# Substring boost (v3/EXP1)
# ---------------------------------------------------------------------------

def substring_boost(
    containment_score: float,
    local_title_norm: str,
    sc_track: dict,
    penalties_clean: bool,
) -> tuple[float, bool]:
    if not local_title_norm or not penalties_clean:
        return containment_score, False

    title_words = [
        w for w in local_title_norm.split()
        if w and not w.isdigit() and len(w) >= 2
        and w not in NOISE_WORDS and w not in ARTICLE_WORDS
    ]
    if len(title_words) < 2:
        return containment_score, False

    sc_title = sc_track.get("title") or ""
    sc_full_norm = normalize_for_substring(strip_bracket_suffixes(sc_title))
    sc_real_norm = normalize_for_substring(parse_sc_real_title(sc_title))
    sc_artist = sc_track.get("artist") or ""
    sc_with_artist = normalize_for_substring(f"{sc_artist} {strip_bracket_suffixes(sc_title)}")

    local_in_sc = (
        local_title_norm in sc_full_norm
        or local_title_norm in sc_real_norm
        or local_title_norm in sc_with_artist
    )
    sc_in_local = bool(sc_real_norm and len(sc_real_norm) >= 4 and sc_real_norm in local_title_norm)

    if not (local_in_sc or sc_in_local):
        return containment_score, False

    blended = 0.5 * containment_score + 0.5 * 1.0
    return max(containment_score, blended), True


# ---------------------------------------------------------------------------
# Levenshtein boost (v3/EXP4)
# ---------------------------------------------------------------------------

def levenshtein_distance(s1: str, s2: str) -> int:
    m, n = len(s1), len(s2)
    if m > n:
        s1, s2 = s2, s1
        m, n = n, m
    prev = list(range(m + 1))
    for j in range(1, n + 1):
        curr = [j] + [0] * m
        for i in range(1, m + 1):
            if s1[i - 1] == s2[j - 1]:
                curr[i] = prev[i - 1]
            else:
                curr[i] = 1 + min(prev[i - 1], prev[i], curr[i - 1])
        prev = curr
    return prev[m]


def normalized_levenshtein(s1: str, s2: str) -> float:
    if not s1 and not s2:
        return 1.0
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    dist = levenshtein_distance(s1, s2)
    return 1.0 - dist / max_len


def levenshtein_boost(
    local_track: dict,
    sc_track: dict,
    score: float,
) -> tuple[float, float]:
    if score >= 0.90:
        return score, 0.0

    local_title = normalize_text(local_track.get("title") or "")
    local_artist = normalize_text(local_track.get("artist") or "")
    sc_full_title = normalize_text(sc_track.get("title") or "")

    local_combined = f"{local_artist} {local_title}" if local_artist else local_title
    lev_score = normalized_levenshtein(local_combined, sc_full_title)

    if lev_score > 0.80:
        boosted = 0.6 * score + 0.4 * lev_score
        return max(score, boosted), lev_score

    return score, lev_score


# ---------------------------------------------------------------------------
# EXP8: Filename-as-ground-truth scoring
# ---------------------------------------------------------------------------

def filename_containment_score(
    filename_tokens: set[str],
    sc_tokens: set[str],
    sc_real_tokens: set[str],
) -> float:
    if not filename_tokens:
        return 0.0

    int_full = filename_tokens & sc_tokens
    int_real = filename_tokens & sc_real_tokens
    if len(int_real) >= len(int_full):
        intersection = int_real
        used = sc_real_tokens
    else:
        intersection = int_full
        used = sc_tokens

    base = len(intersection) / len(filename_tokens)

    noise_penalty = 1.0
    if len(used) > 2.5 * len(filename_tokens):
        noise_penalty = 0.85

    reverse_remix_penalty = 1.0
    fn_has_remix = has_remix_indicators(filename_tokens)
    sc_has_remix = has_remix_indicators(used) or has_remix_indicators(sc_tokens)
    if sc_has_remix and not fn_has_remix:
        reverse_remix_penalty = 0.5

    return min(1.0, base * noise_penalty * reverse_remix_penalty)


def filename_substring_boost(
    fn_score: float,
    filename_clean_norm: str,
    sc_track: dict,
) -> tuple[float, bool]:
    if not filename_clean_norm or len(filename_clean_norm) < 3:
        return fn_score, False

    fn_words = [
        w for w in filename_clean_norm.split()
        if w and len(w) >= 2 and w not in NOISE_WORDS and w not in ARTICLE_WORDS
    ]
    if len(fn_words) < 2:
        return fn_score, False

    sc_title = sc_track.get("title") or ""
    sc_artist = sc_track.get("artist") or ""
    sc_full_norm = normalize_for_substring(strip_bracket_suffixes(sc_title))
    sc_real_norm = normalize_for_substring(parse_sc_real_title(sc_title))
    sc_with_artist = normalize_for_substring(f"{sc_artist} {strip_bracket_suffixes(sc_title)}")

    fn_in_sc = (
        filename_clean_norm in sc_full_norm
        or filename_clean_norm in sc_real_norm
        or filename_clean_norm in sc_with_artist
    )
    sc_in_fn = bool(sc_real_norm and len(sc_real_norm) >= 3 and sc_real_norm in filename_clean_norm)

    if not (fn_in_sc or sc_in_fn):
        return fn_score, False

    blended = 0.5 * fn_score + 0.5 * 1.0
    return max(fn_score, blended), True


def score_filename_path(
    local_track: dict,
    sc_tracks: list[dict],
    candidates: list[tuple[int, float]],
) -> tuple[dict | None, float, dict]:
    path = local_track.get("local_path", "")
    if not path:
        return None, 0.0, {}

    raw_stem = Path(path).stem
    cleaned_stem = clean_filename_stem(raw_stem)
    filename_tokens = tokenize(cleaned_stem)
    filename_clean_norm = normalize_for_substring(cleaned_stem)

    if len(filename_tokens) < 2:
        return None, 0.0, {}

    if not candidates:
        return None, 0.0, {}

    best_match = None
    best_score = 0.0
    best_debug: dict = {}

    for idx, tfidf_s in candidates:
        sc = sc_tracks[idx]
        sc_tokens_all, sc_real_tokens, _ = sc_track_tokens(sc)

        fn_cont = filename_containment_score(filename_tokens, sc_tokens_all, sc_real_tokens)
        fn_final, fn_substr = filename_substring_boost(fn_cont, filename_clean_norm, sc)

        if fn_final > best_score:
            best_score = fn_final
            best_match = sc
            best_debug = {
                "fn_containment": fn_cont,
                "fn_substr_boosted": fn_substr,
                "fn_tokens": sorted(filename_tokens),
                "fn_cleaned": cleaned_stem,
                "fn_tfidf": tfidf_s,
            }

    return best_match, best_score, best_debug


# ---------------------------------------------------------------------------
# Main matching (v4: v3 + EXP8)
# ---------------------------------------------------------------------------

def match_track(
    local_track: dict,
    sc_tracks: list[dict],
    vectorizer: TfidfVectorizer,
    sc_matrix: np.ndarray,
) -> tuple[dict | None, float, str]:
    """Match a local track against SC tracks. Returns (best_sc, score, scoring_path)."""
    local_tokens, critical_tokens, local_artist_tokens = local_track_tokens(local_track)
    local_title_norm = normalize_for_substring(local_track.get("title") or "")

    candidates = tfidf_top_k(local_track, vectorizer, sc_matrix, k=10)
    if not candidates:
        return None, 0.0, "no_candidates"

    # --- V3 path: title+artist+filename combined ---
    best_v3_match = None
    best_v3_score = 0.0
    best_v3_path = "v3"

    for idx, tfidf_s in candidates:
        sc = sc_tracks[idx]
        sc_tokens_all, sc_real_tokens, sc_artist_tokens = sc_track_tokens(sc)

        containment_s, score_debug = containment_score_with_penalty(
            local_tokens, critical_tokens, sc_tokens_all, sc_real_tokens,
            local_artist_tokens, sc_artist_tokens,
        )

        penalties_clean = (
            score_debug["critical_penalty"] >= 1.0
            and score_debug["reverse_remix_penalty"] >= 1.0
        )
        score_after_substr, was_substr_boosted = substring_boost(
            containment_s, local_title_norm, sc, penalties_clean,
        )

        final_score, lev_score = levenshtein_boost(local_track, sc, score_after_substr)

        if final_score > best_v3_score:
            best_v3_score = final_score
            best_v3_match = sc
            boosts = ["v3"]
            if was_substr_boosted:
                boosts.append("substr")
            if final_score > score_after_substr:
                boosts.append(f"lev={lev_score:.2f}")
            if score_debug.get("artist_boost", 1.0) > 1.0:
                boosts.append("artist_boost")
            best_v3_path = "+".join(boosts)

    # --- EXP8: Filename path (reuses same TF-IDF candidates) ---
    fn_match, fn_score, fn_debug = score_filename_path(
        local_track, sc_tracks, candidates,
    )

    if fn_score > best_v3_score:
        fn_boosts = ["filename"]
        if fn_debug.get("fn_substr_boosted"):
            fn_boosts.append("fn_substr")
        scoring_path = "+".join(fn_boosts)
        return fn_match, fn_score, scoring_path

    return best_v3_match, best_v3_score, best_v3_path


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def fetch_local_tracks(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT id, title, artist, local_path
        FROM tracks
        WHERE (source = 'local' OR source = 'file')
          AND local_path IS NOT NULL
          AND soundcloud_id IS NULL
    """).fetchall()
    return [dict(r) for r in rows]


def fetch_sc_tracks(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT id, title, artist, soundcloud_id
        FROM tracks
        WHERE source = 'soundcloud'
          AND soundcloud_id IS NOT NULL
          AND local_path IS NULL
    """).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill SoundCloud IDs for unlinked local tracks (v4 algorithm)."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Write changes to DB (default: dry-run, print counts only).",
    )
    args = parser.parse_args()

    dry_run = not args.apply
    mode_label = "DRY-RUN" if dry_run else "APPLY"
    logger.info(f"backfill_sc_matches starting — mode={mode_label}")

    from music_minion.core.database import init_database
    init_database()

    with get_db_connection() as conn:
        local_tracks = fetch_local_tracks(conn)
        sc_tracks = fetch_sc_tracks(conn)

    logger.info(f"Local unlinked tracks : {len(local_tracks)}")
    logger.info(f"SoundCloud tracks     : {len(sc_tracks)}")

    if not sc_tracks:
        logger.warning("No SoundCloud tracks found — nothing to match against.")
        return

    if not local_tracks:
        logger.info("No unlinked local tracks — nothing to do.")
        return

    logger.info("Building TF-IDF index...")
    vectorizer, sc_matrix = build_tfidf_index(sc_tracks)
    logger.info(f"TF-IDF index built. Shape: {sc_matrix.shape}")

    logger.info("Running v4 matching...")

    auto_links: list[tuple[int, str]] = []       # (local_id, sc_soundcloud_id)
    candidates: list[tuple[int, int, float, str]] = []  # (local_id, sc_id, score, path)
    unmatched_count = 0

    for i, lt in enumerate(local_tracks):
        if i > 0 and i % 500 == 0:
            pct = i / len(local_tracks) * 100
            logger.info(f"  Progress: {i}/{len(local_tracks)} ({pct:.0f}%)")

        best_sc, score, scoring_path = match_track(lt, sc_tracks, vectorizer, sc_matrix)

        if best_sc is None or score < 0.50:
            unmatched_count += 1
            continue

        if score >= 0.90:
            auto_links.append((lt["id"], best_sc["soundcloud_id"]))
        else:
            candidates.append((lt["id"], best_sc["id"], score, scoring_path))

    total = len(local_tracks)
    logger.info(f"  Progress: {total}/{total} (100%) — done")

    # --- Summary ---
    print()
    print("=" * 60)
    print(f"BACKFILL RESULTS  [{mode_label}]")
    print("=" * 60)
    print(f"  Local unlinked tracks : {total}")
    print(f"  SC tracks in index    : {len(sc_tracks)}")
    print()
    print(f"  Auto-link  (>=0.90)   : {len(auto_links)}")
    print(f"  Candidates (0.50-0.89): {len(candidates)}")
    print(f"  Unmatched  (<0.50)    : {unmatched_count}")
    print("=" * 60)

    if dry_run:
        print()
        print("Dry-run — no changes written. Pass --apply to commit.")
        logger.info("Dry-run complete. No DB changes made.")
        return

    # --- Write to DB in a single transaction ---
    logger.info("Writing changes to database...")

    with get_db_connection() as conn:
        # Auto-links: set soundcloud_id on local track
        # Use INSERT OR IGNORE pattern to skip duplicates caused by
        # UNIQUE(source, soundcloud_id) when multiple local tracks
        # match the same SC track.
        link_skipped = 0
        for local_id, sc_soundcloud_id in auto_links:
            try:
                conn.execute(
                    "UPDATE tracks SET soundcloud_id = ? WHERE id = ?",
                    (sc_soundcloud_id, local_id),
                )
            except sqlite3.IntegrityError:
                link_skipped += 1
        if link_skipped:
            logger.warning(f"Skipped {link_skipped} auto-links due to duplicate soundcloud_id")

        # Candidates: insert into match_candidates (ignore duplicates)
        for local_id, sc_id, score, scoring_path in candidates:
            conn.execute(
                """
                INSERT OR IGNORE INTO match_candidates
                    (local_track_id, sc_track_id, score, scoring_path)
                VALUES (?, ?, ?, ?)
                """,
                (local_id, sc_id, round(score, 6), scoring_path),
            )

        conn.commit()

    logger.info(
        f"Done. Auto-linked: {len(auto_links)}, "
        f"Candidates inserted: {len(candidates)}, "
        f"Unmatched: {unmatched_count}"
    )
    print()
    print(f"Applied: {len(auto_links)} auto-links, {len(candidates)} candidates inserted.")


if __name__ == "__main__":
    main()
