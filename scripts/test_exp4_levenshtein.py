"""Experiment 4: Levenshtein Distance Boost for Mid-Range Scores

Hypothesis: Tracks scoring 0.50-0.89 via token containment can be rescued
by edit-distance similarity on the actual title strings.

Changes vs test_strategy_merged_v2.py:
- Add normalized_levenshtein(s1, s2) — pure DP, no external lib
- In match_track(), after containment scoring, compute levenshtein on:
    * cleaned local title  vs  SC real_title
    * "{artist} - {title}" vs  SC full title
  Take the better of the two lev scores.
- Boost: if containment_score < 0.90 AND lev_score > 0.80:
    boosted = 0.6 * containment + 0.4 * lev
    final   = max(containment, boosted)  — never hurts

Run with: uv run python scripts/test_exp4_levenshtein.py
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
# Constants (unchanged from v2)
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
# Normalization helpers (unchanged)
# ---------------------------------------------------------------------------

def normalize_text(s: str | None) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^\w\s&#]", " ", s)
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


# ---------------------------------------------------------------------------
# Synonym normalization + tokenization (unchanged)
# ---------------------------------------------------------------------------

SYNONYM_MAP = {
    "ft": "feat",
    "featuring": "feat",
    "and": "&",
    "x": "&",
}


def normalize_synonyms(tokens: set[str]) -> set[str]:
    result: set[str] = set()
    for tok in tokens:
        result.add(SYNONYM_MAP.get(tok, tok))
    return result


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


def local_track_tokens(track: dict) -> tuple[set[str], set[str]]:
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


def sc_track_tokens(track: dict) -> tuple[set[str], set[str]]:
    title = track.get("title") or ""
    artist = track.get("artist") or ""
    full_tokens = tokenize(f"{title} {artist}")
    real_title = parse_sc_real_title(title)
    real_tokens = tokenize(f"{real_title} {artist}")
    combined = full_tokens | real_tokens
    return combined, real_tokens


def has_remix_indicators(tokens: set[str]) -> bool:
    non_vip_remix = REMIX_INDICATORS - {"vip"}
    return bool(tokens & non_vip_remix)


# ---------------------------------------------------------------------------
# TF-IDF index (unchanged)
# ---------------------------------------------------------------------------

def build_tfidf_index(sc_tracks: list[dict]) -> tuple[TfidfVectorizer, np.ndarray]:
    strings = []
    for t in sc_tracks:
        artist = t.get("artist", "") or ""
        title = t.get("title", "") or ""
        real_title = parse_sc_real_title(title)
        combined = normalize_text(f"{artist} {title} {real_title}")
        strings.append(combined)
    vectorizer = TfidfVectorizer(min_df=1, ngram_range=(1, 2), lowercase=True, analyzer="word")
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
# Containment scoring (unchanged from v2)
# ---------------------------------------------------------------------------

def containment_score_with_penalty(
    local_tokens: set[str],
    critical_tokens: set[str],
    sc_tokens: set[str],
    sc_real_tokens: set[str],
    local_title: str = "",
    local_artist: str = "",
) -> tuple[float, dict]:
    if not local_tokens:
        return 0.0, {
            "base": 0.0,
            "critical_penalty": 1.0,
            "noise_penalty": 1.0,
            "reverse_remix_penalty": 1.0,
            "intersection": set(),
            "used_sc_tokens": sc_tokens,
            "missing_critical": set(),
        }

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
    else:
        missing_critical = set()

    noise_penalty = 1.0
    if len(used_sc_tokens) > 2.5 * len(local_tokens):
        noise_penalty = 0.85

    reverse_remix_penalty = 1.0
    sc_has_remix = has_remix_indicators(used_sc_tokens)
    sc_has_remix = sc_has_remix or has_remix_indicators(sc_tokens)
    local_has_remix = has_remix_indicators(local_tokens)
    if sc_has_remix and not local_has_remix:
        reverse_remix_penalty = 0.5

    final = base * critical_penalty * noise_penalty * reverse_remix_penalty

    debug = {
        "base": base,
        "critical_penalty": critical_penalty,
        "noise_penalty": noise_penalty,
        "reverse_remix_penalty": reverse_remix_penalty,
        "intersection": intersection,
        "used_sc_tokens": used_sc_tokens,
        "missing_critical": missing_critical,
    }
    return final, debug


# ---------------------------------------------------------------------------
# NEW: Levenshtein distance boost
# ---------------------------------------------------------------------------

def levenshtein_distance(s1: str, s2: str) -> int:
    """Compute edit distance between two strings via DP."""
    m, n = len(s1), len(s2)
    # Optimize: ensure s1 is the shorter string for memory
    if m > n:
        s1, s2 = s2, s1
        m, n = n, m
    # Single row DP (O(min(m,n)) space)
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
    """Return 1.0 - (edit_distance / max_len), clamped to [0, 1].

    Empty strings → 1.0 (identical).
    """
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
    containment_score: float,
) -> tuple[float, float]:
    """Apply Levenshtein boost to mid-range containment scores.

    Returns (final_score, lev_score_used).
    - If containment_score >= 0.90: unchanged (already good).
    - If lev_score > 0.80: boosted = 0.6*containment + 0.4*lev, take max.
    """
    if containment_score >= 0.90:
        return containment_score, 0.0

    local_title = normalize_text(local_track.get("title") or "")
    local_artist = normalize_text(local_track.get("artist") or "")

    sc_full_title = normalize_text(sc_track.get("title") or "")
    sc_real = normalize_text(parse_sc_real_title(sc_track.get("title") or ""))

    # Compare 1: local title vs SC real title
    lev1 = normalized_levenshtein(local_title, sc_real)

    # Compare 2: "artist - title" vs SC full title
    local_combined = normalize_text(f"{local_artist} - {local_title}") if local_artist else local_title
    lev2 = normalized_levenshtein(local_combined, sc_full_title)

    lev_score = max(lev1, lev2)

    if lev_score > 0.80:
        boosted = 0.6 * containment_score + 0.4 * lev_score
        final = max(containment_score, boosted)
        return final, lev_score

    return containment_score, lev_score


# ---------------------------------------------------------------------------
# Main matching function (modified to apply lev boost)
# ---------------------------------------------------------------------------

def match_track(
    local_track: dict,
    sc_tracks: list[dict],
    vectorizer: TfidfVectorizer,
    sc_matrix: np.ndarray,
) -> tuple[dict | None, float, dict]:
    """Find best SC match using TF-IDF + containment scoring + Levenshtein boost."""
    local_tokens, critical_tokens = local_track_tokens(local_track)

    candidates = tfidf_top_k(local_track, vectorizer, sc_matrix, k=10)
    if not candidates:
        return None, 0.0, {}

    best_match = None
    best_score = 0.0
    best_debug: dict = {}

    for idx, tfidf_s in candidates:
        sc = sc_tracks[idx]
        sc_tokens, sc_real_tokens = sc_track_tokens(sc)
        containment_s, score_debug = containment_score_with_penalty(
            local_tokens, critical_tokens, sc_tokens, sc_real_tokens,
            local_title=local_track.get("title", "") or "",
            local_artist=local_track.get("artist", "") or "",
        )

        # Apply Levenshtein boost for mid-range scores
        final_score, lev_score = levenshtein_boost(local_track, sc, containment_s)

        if final_score > best_score:
            best_score = final_score
            best_match = sc
            best_debug = {
                "tfidf": tfidf_s,
                "score": final_score,
                "containment_score": containment_s,
                "lev_score": lev_score,
                "lev_boosted": final_score > containment_s,
                "local_tokens": local_tokens,
                "critical_tokens": critical_tokens,
                "sc_tokens": score_debug["used_sc_tokens"],
                "intersection": score_debug["intersection"],
                "base": score_debug["base"],
                "critical_penalty": score_debug["critical_penalty"],
                "noise_penalty": score_debug["noise_penalty"],
                "reverse_remix_penalty": score_debug["reverse_remix_penalty"],
                "missing_critical": score_debug["missing_critical"],
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
    mc = debug.get("missing_critical", set())
    containment_s = debug.get("containment_score", score)
    lev_score = debug.get("lev_score", 0.0)
    lev_boosted = debug.get("lev_boosted", False)

    boost_str = f" [LEV BOOST: containment={containment_s:.3f} lev={lev_score:.3f}]" if lev_boosted else ""
    penalty_str = f"crit_pen={cp:.1f} noise_pen={np_:.2f} rev_remix_pen={rrp:.1f}"
    lines = [
        f"  [{score:.3f}]{boost_str} base={base:.3f} {penalty_str}",
        f"    LOCAL: {local_label}",
        f"    SC:    {sc_label}",
        f"    shared={sorted(intersection)}",
        f"    miss  ={sorted(missed)}",
        f"    extra ={sorted(extra)}",
    ]
    if mc:
        lines.append(f"    miss_critical={sorted(mc)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# v2 scoring (for delta comparison — replicates v2 without lev boost)
# ---------------------------------------------------------------------------

def tokenize_v1(text: str) -> set[str]:
    normalized = normalize_text(text)
    tokens: set[str] = set()
    for tok in normalized.split():
        if tok.isdigit():
            continue
        if len(tok) < 2:
            continue
        if tok in NOISE_WORDS or tok in ARTICLE_WORDS:
            continue
        tokens.add(tok)
    return tokens


def clean_filename_stem_v1(stem: str) -> str:
    stem = MONTH_PREFIX_RE.sub("", stem)
    stem = ISO_DATE_PREFIX_RE.sub("", stem)
    stem = TRACK_NUM_PREFIX_RE.sub("", stem)
    stem = re.sub(r"^\d{1,3}\s+", "", stem)
    return stem


def local_track_tokens_v1(track: dict) -> tuple[set[str], set[str]]:
    title = track.get("title") or ""
    artist = track.get("artist") or ""
    path = track.get("local_path", "")
    parts = []
    if title:
        parts.append(title)
    if artist:
        parts.append(artist)
    if path:
        stem = clean_filename_stem_v1(Path(path).stem)
        parts.append(stem)
    all_tokens = tokenize_v1(" ".join(parts))
    critical = get_critical_tokens(title, artist)
    return all_tokens, critical


def sc_track_tokens_v1(track: dict) -> tuple[set[str], set[str]]:
    title = track.get("title") or ""
    artist = track.get("artist") or ""
    full_tokens = tokenize_v1(f"{title} {artist}")
    real_title = parse_sc_real_title(title)
    real_tokens = tokenize_v1(f"{real_title} {artist}")
    return full_tokens | real_tokens, real_tokens


def containment_score_v1(
    local_tokens: set[str],
    critical_tokens: set[str],
    sc_tokens: set[str],
    sc_real_tokens: set[str],
) -> float:
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
    return base * critical_penalty * noise_penalty


def score_v1(local_track: dict, sc: dict) -> float:
    local_tokens, critical_tokens = local_track_tokens_v1(local_track)
    sc_tokens, sc_real_tokens = sc_track_tokens_v1(sc)
    return containment_score_v1(local_tokens, critical_tokens, sc_tokens, sc_real_tokens)


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

    print("\nMatching local tracks → SC (with Levenshtein boost)...")
    results: list[tuple[dict, dict | None, float, dict]] = []

    boost_count = 0
    for i, lt in enumerate(local_tracks):
        if i > 0 and i % 500 == 0:
            pct = i / len(local_tracks) * 100
            print(f"  {i:>5}/{len(local_tracks)} ({pct:.0f}%)")

        best_sc, score, debug = match_track(lt, sc_tracks, vectorizer, sc_matrix)
        results.append((lt, best_sc, score, debug))
        if debug.get("lev_boosted"):
            boost_count += 1

    print(f"  {len(local_tracks)}/{len(local_tracks)} (100%) — done")
    print(f"  Levenshtein boosts applied: {boost_count} tracks\n")

    # --- Bucket distribution ---
    by_bucket: dict[str, list] = {k: [] for k in BUCKET_KEYS}
    counts: Counter = Counter()

    for lt, sc, score, debug in results:
        b = bucket_for(score)
        by_bucket[b].append((lt, sc, score, debug))
        counts[b] += 1

    total = len(results)
    print("=" * 60)
    print("CONFIDENCE DISTRIBUTION (Exp4 — Levenshtein Boost)")
    print("=" * 60)
    for b in BUCKET_KEYS:
        n = counts[b]
        pct = n / total * 100
        bar = "#" * int(pct / 2)
        print(f"  {b:>10}: {n:>5} ({pct:5.1f}%)  {bar}")

    print("\n" + "=" * 60)
    print("CUMULATIVE COUNTS")
    print("=" * 60)
    BASELINE = {0.90: 71.3, 0.80: 76.3, 0.70: None, 0.50: None}
    for threshold, label in [(0.90, ">=0.90"), (0.80, ">=0.80"), (0.70, ">=0.70"), (0.50, ">=0.50")]:
        cum = sum(1 for _, _, score, _ in results if score >= threshold)
        pct = cum / total * 100
        base_pct = BASELINE.get(threshold)
        if base_pct is not None:
            delta = pct - base_pct
            delta_str = f"  (baseline {base_pct:.1f}%, delta {delta:+.1f}%)"
        else:
            delta_str = ""
        print(f"  {label}: {cum:>5} ({pct:.1f}%){delta_str}")

    # --- Show lev-boosted tracks ---
    boosted_items = [(lt, sc, score, debug) for lt, sc, score, debug in results if debug.get("lev_boosted")]
    print(f"\n{'=' * 60}")
    print(f"LEV-BOOSTED TRACKS ({len(boosted_items)} total, showing up to 20)")
    print("=" * 60)
    for lt, sc, score, debug in boosted_items[:20]:
        print(format_sample(lt, sc, score, debug))

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
                v1_s = score_v1(lt, sc) if sc else 0.0
                spot_results[key] = (lt, sc, score, v1_s, debug)
                found = True
                break
        if not found:
            print("    NOT FOUND in local unlinked tracks")
            spot_results[key] = (None, None, 0.0, 0.0, {})

    # --- Delta vs v1 (original) ---
    print(f"\n{'=' * 60}")
    print("COMPARISON: v1 vs exp4 scores (spot checks)")
    print("=" * 60)
    print(f"  {'Track':<45} {'v1':>6}  {'exp4':>6}  {'delta':>7}")
    print(f"  {'-'*45} {'-'*6}  {'-'*6}  {'-'*7}")

    for title_frag, artist_frag, note in spot_checks:
        key = f"{title_frag}|{artist_frag or ''}"
        lt, sc, exp4_s, v1_s, debug = spot_results.get(key, (None, None, 0.0, 0.0, {}))
        label = f"{title_frag}" + (f" ({artist_frag})" if artist_frag else "")
        delta = exp4_s - v1_s
        delta_str = f"{delta:+.3f}"
        boosted_flag = " *" if debug.get("lev_boosted") else ""
        print(f"  {label:<45} {v1_s:>6.3f}  {exp4_s:>6.3f}  {delta_str:>7}{boosted_flag}")

    print("\n  (* = Levenshtein boost was applied)")


if __name__ == "__main__":
    main()
