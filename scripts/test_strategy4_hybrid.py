"""Strategy 4: Hybrid TF-IDF × Keyword Containment matching.

Combines:
1. TF-IDF cosine similarity to get top-5 candidate SC tracks per local track
2. Keyword containment scoring to re-rank / filter candidates
3. Final score = tfidf_score * 0.5 + (containment * penalty) * 0.5

This avoids brute-force keyword comparison against all ~9000 SC tracks by
using TF-IDF to narrow the field first.
"""

import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from music_minion.domain.library.deduplication import normalize_string

DB_PATH = Path.home() / ".local/share/music-minion/music_minion.db"

# Tokens that carry no semantic meaning for track identity
STOP_WORDS = {
    "free", "download", "dl", "out", "now", "official", "full", "stream",
    "original", "audio", "video", "premiere", "exclusive", "records", "music",
    "set", "ep", "lp", "vol",
}

# Tokens that distinguish a remix/version — if local has these but SC candidate
# doesn't (or vice versa), that's a bad match and should be penalised.
DISTINGUISHING_TOKENS = {"remix", "vip", "bootleg", "edit", "flip", "dub", "instrumental"}


# ---------------------------------------------------------------------------
# String normalisation (shared with existing code via import; kept inline too
# so we can tweak independently without touching production module).
# ---------------------------------------------------------------------------

def _normalize(s: str | None) -> str:
    """Lowercase, strip leading article, remove punctuation."""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"^(the|a|an)\s+", "", s)
    s = re.sub(r"[^\w\s]", " ", s)  # punctuation → space (not removal, catches "feat.")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _strip_featuring(s: str) -> str:
    """Remove (feat. X) / (ft. X) / (featuring X) patterns."""
    s = re.sub(r"\s*\((?:feat\.?|ft\.?|featuring)\s+[^()]+\)", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*\[(?:feat\.?|ft\.?|featuring)\s+[^\[\]]+\]", "", s, flags=re.IGNORECASE)
    return s


def _clean_filename_stem(stem: str) -> str:
    """Strip date prefixes, track numbers from filename stems.

    Examples:
        "Nov 23_Knife Party - LRAD"  -> "Knife Party - LRAD"
        "01 - Boss Mode"             -> "Boss Mode"
        "2014-03-22 Flume"           -> "Flume"
    """
    # Month name + day prefix: "Nov 23_", "Jan 01 "
    stem = re.sub(r"^[A-Za-z]{3,9}\s+\d{1,2}[_ ]", "", stem)
    # ISO date prefix: "2014-03-22 "
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}\s+", "", stem)
    # Track number prefix: "01 - ", "1. ", "01_"
    stem = re.sub(r"^\d+\s*[-–._]\s*", "", stem)
    return stem


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------

def tokenize(text: str) -> set[str]:
    """Return cleaned token set, minus stop words."""
    tokens = set(_normalize(text).split())
    # Remove very short tokens (single chars, etc.) but keep "vip", "dj" etc.
    tokens = {t for t in tokens if len(t) >= 2}
    return tokens - STOP_WORDS


def local_track_tokens(track: dict) -> set[str]:
    """Build token set from local track — title + artist + clean filename stem.

    Deliberately excludes album: album metadata is often wrong or generic
    (e.g., "SoundCloud" / "Beatport Download") and adds noise.
    """
    parts = []
    for field in ("title", "artist"):
        v = track.get(field)
        if v:
            parts.append(v)

    path = track.get("local_path", "")
    if path:
        stem = _clean_filename_stem(Path(path).stem)
        parts.append(stem)

    return tokenize(" ".join(parts))


def sc_track_tokens(track: dict) -> set[str]:
    """Build token set from SC track — title + artist (no filename)."""
    parts = []
    for field in ("title", "artist"):
        v = track.get(field)
        if v:
            parts.append(v)
    return tokenize(" ".join(parts))


# ---------------------------------------------------------------------------
# TF-IDF index (vectorises SC tracks once, queries per local track)
# ---------------------------------------------------------------------------

def build_tfidf_index(
    sc_tracks: list[dict],
) -> tuple[TfidfVectorizer, np.ndarray]:
    """Build TF-IDF matrix over SC tracks.

    Returns (vectorizer, sc_matrix) ready for cosine_similarity queries.
    The SC side has featuring artists stripped to avoid spurious matches to
    "(feat. X)" collateral tokens.
    """
    strings = []
    for t in sc_tracks:
        artist = t.get("artist", "") or ""
        title = t.get("title", "") or ""
        combined = _normalize(_strip_featuring(f"{artist} {title}"))
        strings.append(combined)

    vectorizer = TfidfVectorizer(
        min_df=1,
        ngram_range=(1, 2),
        lowercase=True,
        analyzer="word",
    )
    matrix = vectorizer.fit_transform(strings)
    return vectorizer, matrix


def tfidf_top_k(
    local_track: dict,
    vectorizer: TfidfVectorizer,
    sc_matrix: np.ndarray,
    k: int = 5,
) -> list[tuple[int, float]]:
    """Return indices + tfidf scores for top-k SC candidates for a local track.

    Local side keeps featuring artists (title/artist metadata may lack them,
    but filename often has the full string).
    """
    artist = local_track.get("artist", "") or ""
    title = local_track.get("title", "") or ""
    path = local_track.get("local_path", "")
    filename = _clean_filename_stem(Path(path).stem) if path else ""
    combined = _normalize(f"{artist} {title} {filename}")

    try:
        vec = vectorizer.transform([combined])
    except Exception:
        return []

    sims = cosine_similarity(vec, sc_matrix)[0]

    # argsort ascending → take last k → reverse for descending
    top_indices = np.argsort(sims)[-k:][::-1]
    return [(int(idx), float(sims[idx])) for idx in top_indices if sims[idx] > 0]


# ---------------------------------------------------------------------------
# Keyword containment score
# ---------------------------------------------------------------------------

def containment_score(
    local_tokens: set[str],
    sc_tokens: set[str],
) -> tuple[float, float]:
    """Return (raw_containment, penalty).

    raw_containment = |intersection| / |local_tokens|
        → "what fraction of local's identity tokens did we find in SC?"

    penalty = 0.7 if local has distinguishing tokens (remix/vip/bootleg/edit/flip/
    dub/instrumental) that SC candidate *lacks*, else 1.0.
        → prevents matching "Song (VIP)" to "Song (Original Mix)"
    """
    if not local_tokens or not sc_tokens:
        return 0.0, 1.0

    intersection = local_tokens & sc_tokens
    raw = len(intersection) / len(local_tokens)

    # Penalty: local has a version/remix token the SC candidate doesn't share
    local_dist = local_tokens & DISTINGUISHING_TOKENS
    sc_dist = sc_tokens & DISTINGUISHING_TOKENS
    penalty = 0.7 if local_dist and not (local_dist & sc_dist) else 1.0

    return raw, penalty


# ---------------------------------------------------------------------------
# Hybrid match: TF-IDF top-5 → re-rank with keyword containment
# ---------------------------------------------------------------------------

def hybrid_match(
    local_track: dict,
    sc_tracks: list[dict],
    vectorizer: TfidfVectorizer,
    sc_matrix: np.ndarray,
) -> tuple[dict | None, float, dict]:
    """Find best SC match for a local track using hybrid scoring.

    Returns (best_sc_track, final_score, debug_info).
    """
    local_tokens = local_track_tokens(local_track)

    candidates = tfidf_top_k(local_track, vectorizer, sc_matrix, k=5)
    if not candidates:
        return None, 0.0, {"tfidf": 0.0, "containment": 0.0, "penalty": 1.0}

    best_match = None
    best_final = 0.0
    best_debug: dict = {}

    for idx, tfidf_s in candidates:
        sc = sc_tracks[idx]
        sc_tokens = sc_track_tokens(sc)
        cont, penalty = containment_score(local_tokens, sc_tokens)
        final = tfidf_s * 0.5 + (cont * penalty) * 0.5

        if final > best_final:
            best_final = final
            best_match = sc
            best_debug = {
                "tfidf": tfidf_s,
                "containment": cont,
                "penalty": penalty,
                "local_tokens": local_tokens,
                "sc_tokens": sc_tokens,
            }

    return best_match, best_final, best_debug


# ---------------------------------------------------------------------------
# Bucket helpers
# ---------------------------------------------------------------------------

BUCKET_KEYS = ["0.90+", "0.80-0.89", "0.70-0.79", "0.60-0.69", "0.50-0.59", "< 0.50"]


def bucket_for(score: float) -> str:
    if score >= 0.90:
        return "0.90+"
    if score >= 0.80:
        return "0.80-0.89"
    if score >= 0.70:
        return "0.70-0.79"
    if score >= 0.60:
        return "0.60-0.69"
    if score >= 0.50:
        return "0.50-0.59"
    return "< 0.50"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    local_rows = conn.execute("""
        SELECT id, title, artist, local_path
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

    print(f"Local unlinked tracks : {len(local_tracks)}")
    print(f"SoundCloud tracks     : {len(sc_tracks)}")

    # --- Build TF-IDF index once ---
    print("\nBuilding TF-IDF index over SC tracks...")
    vectorizer, sc_matrix = build_tfidf_index(sc_tracks)
    print("Index built.")

    # --- Match ---
    print("\nMatching local tracks → SC (hybrid)...")
    results: list[tuple[dict, dict | None, float, dict]] = []
    report_interval = max(1, len(local_tracks) // 20)

    for i, lt in enumerate(local_tracks):
        if i % report_interval == 0:
            pct = i / len(local_tracks) * 100
            print(f"  {i:>5}/{len(local_tracks)} ({pct:4.0f}%)")

        best_sc, final_score, debug = hybrid_match(lt, sc_tracks, vectorizer, sc_matrix)
        results.append((lt, best_sc, final_score, debug))

    print(f"  {len(local_tracks)}/{len(local_tracks)} (100%) — done\n")

    # --- Bucket distribution ---
    by_bucket: dict[str, list] = {k: [] for k in BUCKET_KEYS}
    counts = Counter()

    for lt, sc, score, debug in results:
        b = bucket_for(score)
        by_bucket[b].append((lt, sc, score, debug))
        counts[b] += 1

    total = len(results)
    print("=== CONFIDENCE DISTRIBUTION ===")
    for b in BUCKET_KEYS:
        n = counts[b]
        pct = n / total * 100
        bar = "#" * int(pct / 2)
        print(f"  {b:>10}: {n:>5} ({pct:5.1f}%) {bar}")

    print("\n=== CUMULATIVE COUNTS ===")
    for threshold, label in [(0.90, "≥0.90"), (0.80, "≥0.80"), (0.70, "≥0.70"), (0.50, "≥0.50")]:
        cum = sum(counts[b] for b in BUCKET_KEYS if b != "< 0.50" and _bucket_min(b) >= threshold)
        # recount properly
        cum = sum(1 for _, _, score, _ in results if score >= threshold)
        print(f"  {label}: {cum:>5} ({cum/total*100:.1f}%)")

    # --- Samples from each bucket ---
    def show_bucket(bucket_name: str, n: int = 10) -> None:
        items = by_bucket[bucket_name]
        print(f"\n=== {bucket_name} — {len(items)} total, showing {min(n, len(items))} samples ===")
        for lt, sc, score, debug in items[:n]:
            local_label = f"{lt.get('artist') or '?'} — {lt.get('title') or '?'}"
            sc_label = f"{sc['artist']} — {sc['title']}" if sc else "NO MATCH"
            shared = debug.get("local_tokens", set()) & debug.get("sc_tokens", set())
            missed = debug.get("local_tokens", set()) - debug.get("sc_tokens", set())
            tfidf_s = debug.get("tfidf", 0.0)
            cont = debug.get("containment", 0.0)
            pen = debug.get("penalty", 1.0)
            print(f"  [{score:.3f}] tfidf={tfidf_s:.3f} cont={cont:.3f} pen={pen:.1f}")
            print(f"    LOCAL: {local_label}")
            print(f"    SC   : {sc_label}")
            print(f"    shared={shared}  missed={missed}")

    for b in BUCKET_KEYS:
        show_bucket(b, 10)

    # --- Spot checks ---
    print("\n=== SPOT CHECK ===")
    spot_checks = [
        ("LRAD", None),
        ("Nap In The Club", None),
        ("#SELFIE", None),
        ("Hawt", "Brillz"),
        ("The Game", "Curfew"),
        ("Boss Mode", "Knife Party"),
        ("Vincent", None),   # "Vincent - Only"
    ]

    for title_frag, artist_frag in spot_checks:
        for lt, sc, score, debug in results:
            lt_title = (lt.get("title") or "").lower()
            lt_artist = (lt.get("artist") or "").lower()
            title_match = title_frag.lower() in lt_title
            artist_match = artist_frag is None or artist_frag.lower() in lt_artist
            if title_match and artist_match:
                local_label = f"{lt.get('artist') or '?'} — {lt.get('title') or '?'}"
                sc_label = f"{sc['artist']} — {sc['title']}" if sc else "NO MATCH"
                tfidf_s = debug.get("tfidf", 0.0)
                cont = debug.get("containment", 0.0)
                pen = debug.get("penalty", 1.0)
                shared = debug.get("local_tokens", set()) & debug.get("sc_tokens", set())
                missed = debug.get("local_tokens", set()) - debug.get("sc_tokens", set())
                print(f"\n  Searching for: '{title_frag}'" + (f" by '{artist_frag}'" if artist_frag else ""))
                print(f"  [{score:.3f}] tfidf={tfidf_s:.3f} cont={cont:.3f} pen={pen:.1f}")
                print(f"    LOCAL: {local_label}")
                print(f"    SC   : {sc_label}")
                print(f"    shared={shared}  missed={missed}")
                break
        else:
            print(f"\n  Searching for: '{title_frag}'" + (f" by '{artist_frag}'" if artist_frag else ""))
            print("    NOT FOUND in local unlinked tracks")


def _bucket_min(bucket: str) -> float:
    """Return the lower bound of a bucket label (for cumulative calc)."""
    mapping = {
        "0.90+": 0.90,
        "0.80-0.89": 0.80,
        "0.70-0.79": 0.70,
        "0.60-0.69": 0.60,
        "0.50-0.59": 0.50,
        "< 0.50": 0.0,
    }
    return mapping.get(bucket, 0.0)


if __name__ == "__main__":
    main()
