"""Experiment 3: Artist-Weighted Containment Scoring

Based on test_strategy_merged_v2.py — adds artist token weighting to containment score.

Key changes vs baseline (v2):
1. local_track_tokens() now returns (all_tokens, critical_tokens, artist_tokens)
2. sc_track_tokens() now returns (all_tokens, real_title_tokens, sc_artist_tokens)
3. containment_score_with_penalty() uses weighted scoring:
   - Artist tokens that match: count 2x in numerator
   - Artist tokens that don't match: count 2x in denominator
   - Formula: weighted_intersection / weighted_total
4. Exact artist match (ALL local artist tokens found in SC) → 1.1x boost (capped at 1.0)

All other penalties preserved: critical, noise, reverse remix.

Run with: uv run python scripts/test_exp3_artist_weight.py
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

DB_PATH = Path.home() / ".local/share/music-minion/music_minion.db"

# ---------------------------------------------------------------------------
# Constants
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


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def normalize_text(s: str | None) -> str:
    """Lowercase, keep & and #, replace other punctuation with spaces."""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^\w\s&#]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def clean_filename_stem(stem: str) -> str:
    """Strip date/month/album prefixes and track numbers from filename stems."""
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
    """Strip [Free Download], [OUT NOW], [FREE DL] etc. from SC titles."""
    return BRACKET_SUFFIX_RE.sub("", title).strip()


def parse_sc_real_title(sc_title: str) -> str:
    """Extract the real title from SC titles like 'Label - Artist - Real Title'."""
    cleaned = strip_bracket_suffixes(sc_title)
    if " - " in cleaned:
        return cleaned.split(" - ")[-1].strip()
    return cleaned


# ---------------------------------------------------------------------------
# FIX 1: Synonym normalization
# ---------------------------------------------------------------------------

SYNONYM_MAP = {
    "ft": "feat",
    "featuring": "feat",
    "and": "&",
    "x": "&",
}


def normalize_synonyms(tokens: set[str]) -> set[str]:
    """Normalize synonym tokens: ft→feat, featuring→feat, and→&, x→&."""
    result: set[str] = set()
    for tok in tokens:
        result.add(SYNONYM_MAP.get(tok, tok))
    return result


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

def tokenize(text: str) -> set[str]:
    """Normalize text and return clean token set."""
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
    """Extract critical tokens: remix artist, featured artist names."""
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
    """Build token set from local track: title + artist + clean filename stem.

    Returns (all_tokens, critical_tokens, artist_tokens).
    artist_tokens is a subset of all_tokens derived solely from the artist field.
    """
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
    # Artist tokens: tokenize the artist field only
    artist_tokens = tokenize(artist) if artist else set()
    return all_tokens, critical, artist_tokens


def sc_track_tokens(track: dict) -> tuple[set[str], set[str], set[str]]:
    """Build token set from SC track using both full title and parsed real title.

    Returns (all_tokens, real_title_tokens, sc_artist_tokens).
    sc_artist_tokens derived from artist field only.
    """
    title = track.get("title") or ""
    artist = track.get("artist") or ""

    full_tokens = tokenize(f"{title} {artist}")

    real_title = parse_sc_real_title(title)
    real_tokens = tokenize(f"{real_title} {artist}")

    sc_artist_tokens = tokenize(artist) if artist else set()

    combined = full_tokens | real_tokens
    return combined, real_tokens, sc_artist_tokens


def has_remix_indicators(tokens: set[str]) -> bool:
    """Return True if any REMIX_INDICATORS (excluding 'vip') appear in tokens."""
    non_vip_remix = REMIX_INDICATORS - {"vip"}
    return bool(tokens & non_vip_remix)


# ---------------------------------------------------------------------------
# TF-IDF index
# ---------------------------------------------------------------------------

def build_tfidf_index(sc_tracks: list[dict]) -> tuple[TfidfVectorizer, np.ndarray]:
    """Build TF-IDF matrix over SC tracks (title + artist, normalized)."""
    strings = []
    for t in sc_tracks:
        artist = t.get("artist", "") or ""
        title = t.get("title", "") or ""
        real_title = parse_sc_real_title(title)
        combined = normalize_text(f"{artist} {title} {real_title}")
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
    k: int = 10,
) -> list[tuple[int, float]]:
    """Return indices + tfidf scores for top-k SC candidates for a local track."""
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
# EXP3: Artist-Weighted Containment Scoring
# ---------------------------------------------------------------------------

def containment_score_with_penalty(
    local_tokens: set[str],
    critical_tokens: set[str],
    sc_tokens: set[str],
    sc_real_tokens: set[str],
    local_artist_tokens: set[str],
    sc_artist_tokens: set[str],
    local_title: str = "",
    local_artist: str = "",
) -> tuple[float, dict]:
    """Score how well SC candidate covers local track tokens.

    EXP3 changes vs baseline:
    - Artist tokens weighted 2x in both numerator and denominator
    - weighted_intersection / weighted_total replaces |intersection| / |local_tokens|
    - If ALL local artist tokens match SC artist → 1.1x boost (capped at 1.0)

    Preserved penalties: critical, noise, reverse remix.
    """
    if not local_tokens:
        return 0.0, {
            "base": 0.0, "critical_penalty": 1.0, "noise_penalty": 1.0,
            "reverse_remix_penalty": 1.0, "artist_boost": 1.0,
        }

    # Choose the better-matching SC token set (full vs real_title)
    intersection_full = local_tokens & sc_tokens
    intersection_real = local_tokens & sc_real_tokens
    if len(intersection_real) >= len(intersection_full):
        intersection = intersection_real
        used_sc_tokens = sc_real_tokens
    else:
        intersection = intersection_full
        used_sc_tokens = sc_tokens

    # --- EXP3: Weighted base score ---
    # Non-artist local tokens
    non_artist_local = local_tokens - local_artist_tokens

    # Artist tokens that match
    artist_matched = local_artist_tokens & used_sc_tokens
    # Artist tokens that don't match
    artist_missed = local_artist_tokens - used_sc_tokens

    # Non-artist tokens that match
    non_artist_matched = non_artist_local & used_sc_tokens

    # Weighted numerator: artist matches count 2x, others count 1x
    weighted_num = len(artist_matched) * 2 + len(non_artist_matched)

    # Weighted denominator: artist tokens count 2x, others count 1x
    weighted_denom = len(local_artist_tokens) * 2 + len(non_artist_local)

    if weighted_denom == 0:
        base = 0.0
    else:
        base = weighted_num / weighted_denom

    # --- Artist exact-match boost ---
    # If ALL local artist tokens are present in SC tokens → 1.1x boost
    artist_boost = 1.0
    if local_artist_tokens and local_artist_tokens.issubset(used_sc_tokens | sc_artist_tokens):
        artist_boost = 1.1

    # --- Critical token penalty ---
    critical_penalty = 1.0
    actual_critical = critical_tokens - REMIX_INDICATORS - FEAT_INDICATORS
    if actual_critical:
        missing_critical = actual_critical - used_sc_tokens
        if missing_critical:
            critical_penalty = 0.5
    else:
        missing_critical = set()

    # --- Noise penalty ---
    noise_penalty = 1.0
    if len(used_sc_tokens) > 2.5 * len(local_tokens):
        noise_penalty = 0.85

    # --- FIX 2: Reverse remix penalty ---
    reverse_remix_penalty = 1.0
    sc_has_remix = has_remix_indicators(used_sc_tokens) or has_remix_indicators(sc_tokens)
    local_has_remix = has_remix_indicators(local_tokens)
    if sc_has_remix and not local_has_remix:
        reverse_remix_penalty = 0.5

    # Final score — cap at 1.0 after artist boost
    raw_final = base * critical_penalty * noise_penalty * reverse_remix_penalty * artist_boost
    final = min(1.0, raw_final)

    debug = {
        "base": base,
        "critical_penalty": critical_penalty,
        "noise_penalty": noise_penalty,
        "reverse_remix_penalty": reverse_remix_penalty,
        "artist_boost": artist_boost,
        "intersection": intersection,
        "used_sc_tokens": used_sc_tokens,
        "missing_critical": missing_critical,
        "artist_matched": artist_matched,
        "artist_missed": artist_missed,
        "weighted_num": weighted_num,
        "weighted_denom": weighted_denom,
    }
    return final, debug


# ---------------------------------------------------------------------------
# Main matching function
# ---------------------------------------------------------------------------

def match_track(
    local_track: dict,
    sc_tracks: list[dict],
    vectorizer: TfidfVectorizer,
    sc_matrix: np.ndarray,
) -> tuple[dict | None, float, dict]:
    """Find best SC match using TF-IDF + artist-weighted containment scoring."""
    local_tokens, critical_tokens, local_artist_tokens = local_track_tokens(local_track)

    candidates = tfidf_top_k(local_track, vectorizer, sc_matrix, k=10)
    if not candidates:
        return None, 0.0, {}

    best_match = None
    best_score = 0.0
    best_debug: dict = {}

    for idx, tfidf_s in candidates:
        sc = sc_tracks[idx]
        sc_tokens_all, sc_real_tokens, sc_artist_tokens = sc_track_tokens(sc)
        score, score_debug = containment_score_with_penalty(
            local_tokens, critical_tokens, sc_tokens_all, sc_real_tokens,
            local_artist_tokens, sc_artist_tokens,
            local_title=local_track.get("title", "") or "",
            local_artist=local_track.get("artist", "") or "",
        )

        if score > best_score:
            best_score = score
            best_match = sc
            best_debug = {
                "tfidf": tfidf_s,
                "score": score,
                "local_tokens": local_tokens,
                "critical_tokens": critical_tokens,
                "local_artist_tokens": local_artist_tokens,
                "sc_tokens": score_debug["used_sc_tokens"],
                "intersection": score_debug["intersection"],
                "base": score_debug["base"],
                "critical_penalty": score_debug["critical_penalty"],
                "noise_penalty": score_debug["noise_penalty"],
                "reverse_remix_penalty": score_debug["reverse_remix_penalty"],
                "artist_boost": score_debug["artist_boost"],
                "missing_critical": score_debug["missing_critical"],
                "artist_matched": score_debug["artist_matched"],
                "artist_missed": score_debug["artist_missed"],
                "weighted_num": score_debug["weighted_num"],
                "weighted_denom": score_debug["weighted_denom"],
            }

    return best_match, best_score, best_debug


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


def format_sample(lt: dict, sc: dict | None, score: float, debug: dict) -> str:
    local_tokens = debug.get("local_tokens", set())
    sc_tokens = debug.get("sc_tokens", set())
    intersection = debug.get("intersection", local_tokens & sc_tokens)
    missed = local_tokens - sc_tokens
    extra = sc_tokens - local_tokens

    local_label = f"{lt.get('artist') or '?'} - {lt.get('title') or '?'}"
    sc_label = f"{sc['artist']} - {sc['title']}" if sc else "NO MATCH"

    base = debug.get("base", 0.0)
    cp = debug.get("critical_penalty", 1.0)
    np_ = debug.get("noise_penalty", 1.0)
    rrp = debug.get("reverse_remix_penalty", 1.0)
    ab = debug.get("artist_boost", 1.0)
    mc = debug.get("missing_critical", set())
    am = debug.get("artist_matched", set())
    amiss = debug.get("artist_missed", set())

    penalty_str = f"crit={cp:.1f} noise={np_:.2f} rev_remix={rrp:.1f} artist_boost={ab:.1f}"
    lines = [
        f"  [{score:.3f}] base={base:.3f} {penalty_str}",
        f"    LOCAL: {local_label}",
        f"    SC:    {sc_label}",
        f"    shared={sorted(intersection)}",
        f"    miss  ={sorted(missed)}",
        f"    extra ={sorted(extra)}",
        f"    artist_matched={sorted(am)}  artist_missed={sorted(amiss)}",
    ]
    if mc:
        lines.append(f"    miss_critical={sorted(mc)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Baseline v2 scoring (for delta comparison)
# ---------------------------------------------------------------------------

def local_track_tokens_v2(track: dict) -> tuple[set[str], set[str]]:
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
    return all_tokens, critical


def sc_track_tokens_v2(track: dict) -> tuple[set[str], set[str]]:
    title = track.get("title") or ""
    artist = track.get("artist") or ""
    full_tokens = tokenize(f"{title} {artist}")
    real_title = parse_sc_real_title(title)
    real_tokens = tokenize(f"{real_title} {artist}")
    return full_tokens | real_tokens, real_tokens


def containment_score_v2(
    local_tokens: set[str],
    critical_tokens: set[str],
    sc_tokens: set[str],
    sc_real_tokens: set[str],
) -> float:
    """Baseline v2 scoring for spot-check comparison."""
    if not local_tokens:
        return 0.0

    intersection_full = local_tokens & sc_tokens
    intersection_real = local_tokens & sc_real_tokens
    if len(intersection_real) >= len(intersection_full):
        intersection = intersection_real
        used_sc_tokens = sc_real_tokens
    else:
        intersection = intersection_full
        used_sc_tokens = sc_tokens

    base = len(intersection) / len(local_tokens)

    critical_penalty = 1.0
    actual_critical = critical_tokens - REMIX_INDICATORS - FEAT_INDICATORS
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

    return base * critical_penalty * noise_penalty * reverse_remix_penalty


def score_v2(local_track: dict, sc: dict) -> float:
    """Compute baseline v2 score for a local track + SC track pair."""
    local_tokens, critical_tokens = local_track_tokens_v2(local_track)
    sc_tokens, sc_real_tokens = sc_track_tokens_v2(sc)
    return containment_score_v2(local_tokens, critical_tokens, sc_tokens, sc_real_tokens)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
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

    print(f"Local unlinked tracks : {len(local_tracks)}")
    print(f"SoundCloud tracks     : {len(sc_tracks)}")

    print("\nBuilding TF-IDF index over SC tracks...")
    vectorizer, sc_matrix = build_tfidf_index(sc_tracks)
    print(f"Index built. Matrix shape: {sc_matrix.shape}")

    print("\nMatching local tracks → SC (EXP3: artist-weighted scoring)...")
    results: list[tuple[dict, dict | None, float, dict]] = []

    for i, lt in enumerate(local_tracks):
        if i > 0 and i % 500 == 0:
            pct = i / len(local_tracks) * 100
            print(f"  {i:>5}/{len(local_tracks)} ({pct:.0f}%)")

        best_sc, score, debug = match_track(lt, sc_tracks, vectorizer, sc_matrix)
        results.append((lt, best_sc, score, debug))

    print(f"  {len(local_tracks)}/{len(local_tracks)} (100%) — done\n")

    # --- Bucket distribution ---
    by_bucket: dict[str, list] = {k: [] for k in BUCKET_KEYS}
    counts: Counter = Counter()

    for lt, sc, score, debug in results:
        b = bucket_for(score)
        by_bucket[b].append((lt, sc, score, debug))
        counts[b] += 1

    total = len(results)
    print("=" * 60)
    print("CONFIDENCE DISTRIBUTION  [EXP3: artist-weighted]")
    print("=" * 60)
    for b in BUCKET_KEYS:
        n = counts[b]
        pct = n / total * 100
        bar = "#" * int(pct / 2)
        print(f"  {b:>10}: {n:>5} ({pct:5.1f}%)  {bar}")

    print("\n" + "=" * 60)
    print("CUMULATIVE COUNTS")
    print("=" * 60)
    # Baseline reference
    baseline = {0.90: 71.3, 0.80: 76.3, 0.70: None, 0.50: None}
    for threshold, label in [(0.90, ">=0.90"), (0.80, ">=0.80"), (0.70, ">=0.70"), (0.50, ">=0.50")]:
        cum = sum(1 for _, _, score, _ in results if score >= threshold)
        pct = cum / total * 100
        bl = baseline.get(threshold)
        delta_str = f"  (baseline {bl:.1f}%, delta {pct - bl:+.1f}%)" if bl else ""
        print(f"  {label}: {cum:>5} ({pct:.1f}%){delta_str}")

    # --- Samples ---
    def show_bucket(bucket_name: str, n: int = 10) -> None:
        items = by_bucket[bucket_name]
        print(f"\n{'=' * 60}")
        print(f"BUCKET {bucket_name} — {len(items)} total, showing {min(n, len(items))} samples")
        print("=" * 60)
        for lt, sc, score, debug in items[:n]:
            print(format_sample(lt, sc, score, debug))

    show_bucket("0.90+", 15)
    show_bucket("0.80-0.89", 15)
    show_bucket("0.70-0.79", 15)
    show_bucket("0.60-0.69", 15)
    show_bucket("0.50-0.59", 10)
    show_bucket("< 0.50", 10)

    # --- Spot checks ---
    print(f"\n{'=' * 60}")
    print("SPOT CHECKS")
    print("=" * 60)

    spot_checks = [
        ("LRAD", "Knife Party", "should be LOW — reverse remix penalty"),
        ("Nap In The Club", None, "Two Owls Remix version"),
        ("#SELFIE", None, "Chainsmokers"),
        ("Hawt", "Brillz", ""),
        ("The Game", "Curfew", "low score — no SC match"),
        ("Boss Mode", "Knife Party", ""),
        ("Vincent", None, "Vincent - Only"),
        ("Red Lips", "GTA", "Skrillex Remix"),
        ("Get On Up", "Jauz", "Getter Remix"),
        ("Bun Up The Dance", None, "Dreamer Remix"),
    ]

    spot_results: dict[str, tuple[dict | None, dict | None, float, float, dict]] = {}

    for title_frag, artist_frag, note in spot_checks:
        key = f"{title_frag}|{artist_frag or ''}"
        print(f"\n  >> Searching: '{title_frag}'" + (f" by '{artist_frag}'" if artist_frag else "") + (f"  [{note}]" if note else ""))
        found = False
        for lt, sc, score, debug in results:
            lt_title = (lt.get("title") or "").lower()
            lt_artist = (lt.get("artist") or "").lower()
            title_match = title_frag.lower() in lt_title
            artist_match = artist_frag is None or artist_frag.lower() in lt_artist
            if title_match and artist_match:
                print(format_sample(lt, sc, score, debug))
                v2_s = score_v2(lt, sc) if sc else 0.0
                spot_results[key] = (lt, sc, score, v2_s, debug)
                found = True
                break
        if not found:
            print("    NOT FOUND in local unlinked tracks")
            spot_results[key] = (None, None, 0.0, 0.0, {})

    # --- COMPARISON: baseline v2 vs exp3 ---
    print(f"\n{'=' * 60}")
    print("COMPARISON: baseline v2 vs EXP3 (artist-weighted) scores")
    print("=" * 60)
    print(f"  {'Track':<45} {'v2':>6}  {'exp3':>6}  {'delta':>7}")
    print(f"  {'-'*45} {'-'*6}  {'-'*6}  {'-'*7}")

    for title_frag, artist_frag, note in spot_checks:
        key = f"{title_frag}|{artist_frag or ''}"
        lt, sc, exp3_s, v2_s, _ = spot_results.get(key, (None, None, 0.0, 0.0, {}))
        label = f"{title_frag}" + (f" ({artist_frag})" if artist_frag else "")
        delta = exp3_s - v2_s
        delta_str = f"{delta:+.3f}"
        print(f"  {label:<45} {v2_s:>6.3f}  {exp3_s:>6.3f}  {delta_str:>7}")


if __name__ == "__main__":
    main()
