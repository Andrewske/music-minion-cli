"""Experiment 2: Character Trigram Similarity blended with containment score.

Hypothesis: Token-level matching misses compound words ("bassheadsdelight" vs
"bass heads delight"), slight spelling variations, and cases where tokenization
choices differ. A character-level trigram (3-gram) Jaccard similarity used as a
secondary signal may rescue some of those edge cases.

Change vs baseline (test_strategy_merged_v2.py):
  - New function: char_trigram_sim(s1, s2) → Jaccard of 3-char substring sets
  - Trigram computed over normalized "{artist} {title}" strings for both sides
  - Blend: final_score = 0.7 * containment_score + 0.3 * trigram_score
    Only when trigram_score > 0.3; otherwise keep original containment_score

Run with: uv run python scripts/test_exp2_trigram.py
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
# Constants (unchanged from baseline)
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
    return BRACKET_SUFFIX_RE.sub("", title).strip()


def parse_sc_real_title(sc_title: str) -> str:
    cleaned = strip_bracket_suffixes(sc_title)
    if " - " in cleaned:
        return cleaned.split(" - ")[-1].strip()
    return cleaned


# ---------------------------------------------------------------------------
# FIX 1: Synonym normalization (unchanged)
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


# ---------------------------------------------------------------------------
# Tokenization (unchanged)
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
# NEW: Character trigram similarity
# ---------------------------------------------------------------------------

def char_trigrams(s: str) -> set[str]:
    """Return all 3-character substrings of s (after normalizing whitespace away)."""
    # Collapse whitespace so "bass heads" and "bassheads" share trigrams
    compact = re.sub(r"\s+", "", s)
    if len(compact) < 3:
        return set()
    return {compact[i:i+3] for i in range(len(compact) - 2)}


def char_trigram_sim(s1: str, s2: str) -> float:
    """Jaccard similarity of character 3-gram sets between two normalized strings."""
    t1 = char_trigrams(s1)
    t2 = char_trigrams(s2)
    if not t1 and not t2:
        return 0.0
    union = t1 | t2
    intersection = t1 & t2
    return len(intersection) / len(union)


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
# Containment scoring (unchanged from baseline)
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
        return 0.0, {"base": 0.0, "critical_penalty": 1.0, "noise_penalty": 1.0, "reverse_remix_penalty": 1.0}

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
# Main matching function — WITH trigram blend
# ---------------------------------------------------------------------------

def match_track(
    local_track: dict,
    sc_tracks: list[dict],
    vectorizer: TfidfVectorizer,
    sc_matrix: np.ndarray,
) -> tuple[dict | None, float, dict]:
    """Find best SC match using TF-IDF + containment + trigram blend."""
    local_tokens, critical_tokens = local_track_tokens(local_track)

    # Build normalized string for trigram comparison (local side)
    local_title = local_track.get("title") or ""
    local_artist = local_track.get("artist") or ""
    local_norm_str = normalize_text(f"{local_artist} {local_title}")

    candidates = tfidf_top_k(local_track, vectorizer, sc_matrix, k=10)
    if not candidates:
        return None, 0.0, {}

    best_match = None
    best_score = 0.0
    best_debug: dict = {}

    for idx, tfidf_s in candidates:
        sc = sc_tracks[idx]
        sc_tokens_all, sc_real_tokens = sc_track_tokens(sc)
        containment, score_debug = containment_score_with_penalty(
            local_tokens, critical_tokens, sc_tokens_all, sc_real_tokens,
            local_title=local_title,
            local_artist=local_artist,
        )

        # --- Trigram blend ---
        sc_title = sc.get("title") or ""
        sc_artist = sc.get("artist") or ""
        sc_real_title = parse_sc_real_title(sc_title)
        sc_norm_str = normalize_text(f"{sc_artist} {sc_real_title}")

        tg_sim = char_trigram_sim(local_norm_str, sc_norm_str)

        if tg_sim > 0.3:
            score = 0.7 * containment + 0.3 * tg_sim
        else:
            score = containment

        if score > best_score:
            best_score = score
            best_match = sc
            best_debug = {
                "tfidf": tfidf_s,
                "score": score,
                "containment": containment,
                "trigram_sim": tg_sim,
                "local_tokens": local_tokens,
                "critical_tokens": critical_tokens,
                "sc_tokens": score_debug.get("used_sc_tokens", set()),
                "intersection": score_debug.get("intersection", set()),
                "base": score_debug.get("base", 0.0),
                "critical_penalty": score_debug.get("critical_penalty", 1.0),
                "noise_penalty": score_debug.get("noise_penalty", 1.0),
                "reverse_remix_penalty": score_debug.get("reverse_remix_penalty", 1.0),
                "missing_critical": score_debug.get("missing_critical", set()),
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
    tg = debug.get("trigram_sim", None)
    containment = debug.get("containment", score)

    penalty_str = f"crit_pen={cp:.1f} noise_pen={np_:.2f} rev_remix_pen={rrp:.1f}"
    tg_str = f" tg={tg:.3f}" if tg is not None else ""
    contain_str = f" contain={containment:.3f}" if tg is not None else ""
    lines = [
        f"  [{score:.3f}] base={base:.3f} {penalty_str}{contain_str}{tg_str}",
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
# Baseline scoring (v2 without trigram blend) — for spot-check comparison
# ---------------------------------------------------------------------------

def match_track_baseline(
    local_track: dict,
    sc_tracks: list[dict],
    vectorizer: TfidfVectorizer,
    sc_matrix: np.ndarray,
) -> tuple[dict | None, float, dict]:
    """Baseline match (containment only, no trigram blend)."""
    local_tokens, critical_tokens = local_track_tokens(local_track)

    candidates = tfidf_top_k(local_track, vectorizer, sc_matrix, k=10)
    if not candidates:
        return None, 0.0, {}

    best_match = None
    best_score = 0.0
    best_debug: dict = {}

    for idx, tfidf_s in candidates:
        sc = sc_tracks[idx]
        sc_tokens_all, sc_real_tokens = sc_track_tokens(sc)
        score, score_debug = containment_score_with_penalty(
            local_tokens, critical_tokens, sc_tokens_all, sc_real_tokens,
            local_title=local_track.get("title", "") or "",
            local_artist=local_track.get("artist", "") or "",
        )

        if score > best_score:
            best_score = score
            best_match = sc
            best_debug = score_debug

    return best_match, best_score, best_debug


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

    # --- Match with trigram blend ---
    print("\nMatching local tracks → SC (trigram blend)...")
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
    print("CONFIDENCE DISTRIBUTION (Experiment 2: Trigram Blend)")
    print("=" * 60)
    for b in BUCKET_KEYS:
        n = counts[b]
        pct = n / total * 100
        bar = "#" * int(pct / 2)
        print(f"  {b:>10}: {n:>5} ({pct:5.1f}%)  {bar}")

    print("\n" + "=" * 60)
    print("CUMULATIVE COUNTS")
    print("=" * 60)
    baselines = {0.90: 71.3, 0.80: 76.3, 0.70: None, 0.50: None}
    for threshold, label in [(0.90, ">=0.90"), (0.80, ">=0.80"), (0.70, ">=0.70"), (0.50, ">=0.50")]:
        cum = sum(1 for _, _, score, _ in results if score >= threshold)
        pct = cum / total * 100
        base_pct = baselines.get(threshold)
        delta_str = f"  (baseline {base_pct:.1f}%, delta {pct - base_pct:+.1f}pp)" if base_pct is not None else ""
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
    print("SPOT CHECKS (trigram blend vs baseline)")
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
                # Compute baseline score for comparison
                base_sc, base_score, _ = match_track_baseline(lt, sc_tracks, vectorizer, sc_matrix)
                spot_results[key] = (lt, sc, score, base_score, debug)
                found = True
                break
        if not found:
            print("    NOT FOUND in local unlinked tracks")
            spot_results[key] = (None, None, 0.0, 0.0, {})

    # --- Delta table ---
    print(f"\n{'=' * 60}")
    print("DELTA: baseline v2 vs trigram blend (exp2)")
    print("=" * 60)
    print(f"  {'Track':<45} {'base':>6}  {'exp2':>6}  {'delta':>7}  {'tg':>6}")
    print(f"  {'-'*45} {'-'*6}  {'-'*6}  {'-'*7}  {'-'*6}")

    for title_frag, artist_frag, note in spot_checks:
        key = f"{title_frag}|{artist_frag or ''}"
        lt, sc, exp2_s, base_s, debug = spot_results.get(key, (None, None, 0.0, 0.0, {}))
        label = f"{title_frag}" + (f" ({artist_frag})" if artist_frag else "")
        delta = exp2_s - base_s
        delta_str = f"{delta:+.3f}"
        tg_str = f"{debug.get('trigram_sim', 0.0):.3f}" if debug else "  n/a"
        print(f"  {label:<45} {base_s:>6.3f}  {exp2_s:>6.3f}  {delta_str:>7}  {tg_str:>6}")


if __name__ == "__main__":
    main()
