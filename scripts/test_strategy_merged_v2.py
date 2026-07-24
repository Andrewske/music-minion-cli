"""Strategy Merged v2: TF-IDF candidate selection + SC title parsing + containment scoring
with critical token penalties and 3 new fixes.

Fix 1: "ft"/"feat"/"featuring"/"x"/"and" synonym normalization in tokens
Fix 2: Reverse remix penalty — SC has remix indicators but LOCAL doesn't → 0.5x
Fix 3: Better filename cleaning — underscore splits, album-prefix stripping

Run with: uv run python scripts/test_strategy_merged_v2.py
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

# Indicators that follow the version artist name (remix, flip, vip, etc.)
REMIX_INDICATORS = {"remix", "flip", "vip", "edit", "rework", "bootleg"}

# Indicators that precede featured artist name
FEAT_INDICATORS = {"feat", "ft", "featuring"}

# Bracket suffix patterns to strip from SC titles
BRACKET_SUFFIX_RE = re.compile(
    r"\s*[\[\(](?:free\s*download|out\s*now|free\s*dl|free|dl|out|premiere|exclusive|official)[^\]\)]*[\]\)]",
    flags=re.IGNORECASE,
)

# Month prefix patterns for filename stems
MONTH_PREFIX_RE = re.compile(
    r"^(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\s+\d{1,2}[_ ]",
    flags=re.IGNORECASE,
)
ISO_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\s+")
TRACK_NUM_PREFIX_RE = re.compile(r"^\d+\s*[-–._]\s*")

# FIX 3: Album-name prefix pattern — e.g. "BassHeadsDelight_", "ItsOnTheHouse_", "Nov 23_"
# Strips any "Word(s)/dashes/spaces followed by underscore" prefix at start of stem
ALBUM_PREFIX_RE = re.compile(r"^[A-Za-z\s/\-]+_")


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def normalize_text(s: str | None) -> str:
    """Lowercase, keep & and #, replace other punctuation with spaces."""
    if not s:
        return ""
    s = s.lower()
    # Keep & and # but replace other punctuation with space
    s = re.sub(r"[^\w\s&#]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def clean_filename_stem(stem: str) -> str:
    """Strip date/month/album prefixes and track numbers from filename stems.

    FIX 3 additions:
    - Replace underscores with spaces before processing (handles "dnb_076_seven")
    - Strip album-name prefixes: "BassHeadsDelight_", "ItsOnTheHouse_", etc.

    Examples:
        "Nov 23_Knife Party - LRAD"         -> "Knife Party - LRAD"
        "August 18_Boss Mode"               -> "Boss Mode"
        "01 - Something"                    -> "Something"
        "BassHeadsDelight_Artist - Title"   -> "Artist - Title"
        "dnb_076_seven lions"               -> "seven lions"
        "ItsOnTheHouse_Track Name"          -> "Track Name"
    """
    # FIX 3: Strip album-name prefix (alphanumeric words/spaces/dashes followed by underscore)
    # Apply iteratively in case of multiple prefixes
    for _ in range(3):
        new_stem = ALBUM_PREFIX_RE.sub("", stem)
        if new_stem == stem:
            break
        stem = new_stem

    # Month name + day prefix: "Nov 23_", "August 18 "
    stem = MONTH_PREFIX_RE.sub("", stem)
    # ISO date prefix: "2014-03-22 "
    stem = ISO_DATE_PREFIX_RE.sub("", stem)
    # Track number prefix: "01 - ", "03 "
    stem = TRACK_NUM_PREFIX_RE.sub("", stem)
    # Also handle "03 " (number + space at start without dash)
    stem = re.sub(r"^\d{1,3}\s+", "", stem)

    # FIX 3: Replace underscores with spaces so "dnb_076_seven" → "dnb 076 seven"
    stem = stem.replace("_", " ")
    return stem


def strip_bracket_suffixes(title: str) -> str:
    """Strip [Free Download], [OUT NOW], [FREE DL] etc. from SC titles."""
    return BRACKET_SUFFIX_RE.sub("", title).strip()


def parse_sc_real_title(sc_title: str) -> str:
    """Extract the real title from SC titles like 'Label - Artist - Real Title'.

    If title contains ' - ', take the LAST segment and strip bracket suffixes.
    Also strips bracket suffixes from full title if no dash is found.
    """
    cleaned = strip_bracket_suffixes(sc_title)
    if " - " in cleaned:
        return cleaned.split(" - ")[-1].strip()
    return cleaned


# ---------------------------------------------------------------------------
# FIX 1: Synonym normalization
# ---------------------------------------------------------------------------

# Applied AFTER splitting into tokens, before comparison
SYNONYM_MAP = {
    "ft": "feat",
    "featuring": "feat",
    "and": "&",
    "x": "&",
}


def normalize_synonyms(tokens: set[str]) -> set[str]:
    """Normalize synonym tokens: ft→feat, featuring→feat, and→&, x→&.

    Applied after tokenization so we don't alter the raw text split logic.
    """
    result: set[str] = set()
    for tok in tokens:
        result.add(SYNONYM_MAP.get(tok, tok))
    return result


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

def tokenize(text: str) -> set[str]:
    """Normalize text and return clean token set.

    Removes: noise words, article words, single-char tokens, digit-only tokens.
    Keeps: & and # as valid chars in tokens.
    FIX 1: Applies synonym normalization after token extraction.
    FIX 3: Splits on underscores in addition to spaces.
    """
    normalized = normalize_text(text)
    # FIX 3: replace underscores with spaces so "dnb_076_seven" gets split
    normalized = normalized.replace("_", " ")
    tokens: set[str] = set()
    for tok in normalized.split():
        # Skip digit-only tokens (biggest noise source: "01", "23", "24", "47")
        if tok.isdigit():
            continue
        # Skip single chars
        if len(tok) < 2:
            continue
        # Skip noise words and articles
        if tok in NOISE_WORDS or tok in ARTICLE_WORDS:
            continue
        tokens.add(tok)

    # FIX 1: Normalize synonyms AFTER collecting tokens
    return normalize_synonyms(tokens)


def get_critical_tokens(title: str, artist: str) -> set[str]:
    """Extract critical tokens from local track: remix artist, featured artist names.

    After "remix", "flip", "vip", "edit", "rework", "bootleg": next tokens = remix artist
    After "feat", "ft", "featuring": next tokens = featured artist
    These tokens MUST appear in SC candidate for a good match.
    """
    full_text = normalize_text(f"{title} {artist}")
    raw_tokens = full_text.split()
    critical: set[str] = set()

    # FIX 1: normalize raw_tokens for indicator detection too
    normalized_raw = [SYNONYM_MAP.get(tok, tok) for tok in raw_tokens]

    i = 0
    while i < len(normalized_raw):
        tok = normalized_raw[i]
        if tok in REMIX_INDICATORS or tok in FEAT_INDICATORS:
            # Collect the next tokens until we hit another indicator, close bracket, or end
            j = i + 1
            while j < len(normalized_raw) and normalized_raw[j] not in REMIX_INDICATORS and normalized_raw[j] not in FEAT_INDICATORS:
                candidate = normalized_raw[j]
                # Add non-digit, non-trivial tokens
                if not candidate.isdigit() and len(candidate) >= 2 and candidate not in NOISE_WORDS and candidate not in ARTICLE_WORDS:
                    critical.add(candidate)
                j += 1
            i = j
        else:
            i += 1

    return critical


def local_track_tokens(track: dict) -> tuple[set[str], set[str]]:
    """Build token set from local track: title + artist + clean filename stem.

    Returns (all_tokens, critical_tokens).
    Excludes album deliberately (often wrong/generic).
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
    return all_tokens, critical


def sc_track_tokens(track: dict) -> tuple[set[str], set[str]]:
    """Build token set from SC track using both full title and parsed real title.

    Returns (all_tokens, real_title_tokens).
    """
    title = track.get("title") or ""
    artist = track.get("artist") or ""

    full_tokens = tokenize(f"{title} {artist}")

    real_title = parse_sc_real_title(title)
    real_tokens = tokenize(f"{real_title} {artist}")

    # Union: covers both interpretations
    combined = full_tokens | real_tokens
    return combined, real_tokens


def has_remix_indicators(tokens: set[str]) -> bool:
    """Return True if any REMIX_INDICATORS (excluding 'vip') appear in tokens."""
    # VIP is excluded from the reverse penalty per spec
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
        # Include both full and parsed title for better recall
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
# Containment scoring with critical token penalties
# ---------------------------------------------------------------------------

def containment_score_with_penalty(
    local_tokens: set[str],
    critical_tokens: set[str],
    sc_tokens: set[str],
    sc_real_tokens: set[str],
    local_title: str = "",
    local_artist: str = "",
) -> tuple[float, dict]:
    """Score how well SC candidate covers local track tokens.

    base_score = |intersection| / |local_tokens|  (containment)

    Critical token penalty: if ANY critical token (remix artist, feat artist)
    is missing from SC candidate, multiply by 0.5.
    Exception: if critical token IS the indicator word itself, skip it.

    Noise penalty: if sc_tokens is much larger than local_tokens, multiply by 0.85.

    FIX 2 — Reverse remix penalty:
    If SC candidate has remix/version indicator tokens but LOCAL does NOT have
    ANY such indicators, multiply score by 0.5.
    Exception: "vip" alone does not trigger reverse penalty.
    """
    if not local_tokens:
        return 0.0, {"base": 0.0, "critical_penalty": 1.0, "noise_penalty": 1.0, "reverse_remix_penalty": 1.0}

    # Use the better-matching token set (full vs real_title)
    intersection_full = local_tokens & sc_tokens
    intersection_real = local_tokens & sc_real_tokens
    if len(intersection_real) >= len(intersection_full):
        intersection = intersection_real
        used_sc_tokens = sc_real_tokens
    else:
        intersection = intersection_full
        used_sc_tokens = sc_tokens

    base = len(intersection) / len(local_tokens)

    # Critical token penalty
    critical_penalty = 1.0
    # Filter out the indicator words themselves from critical tokens
    actual_critical = critical_tokens - REMIX_INDICATORS - FEAT_INDICATORS
    if actual_critical:
        missing_critical = actual_critical - used_sc_tokens
        if missing_critical:
            critical_penalty = 0.5
    else:
        missing_critical = set()

    # Noise penalty: SC track is much longer (more tokens) than local
    noise_penalty = 1.0
    if len(used_sc_tokens) > 2.5 * len(local_tokens):
        noise_penalty = 0.85

    # FIX 2: Reverse remix penalty
    # If SC has remix/version indicators but LOCAL has none → penalty
    # "vip" alone is excluded from triggering this penalty
    reverse_remix_penalty = 1.0
    sc_has_remix = has_remix_indicators(used_sc_tokens)
    # Check both the token set AND the full sc_tokens (to catch it in either parse)
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
# Main matching function
# ---------------------------------------------------------------------------

def match_track(
    local_track: dict,
    sc_tracks: list[dict],
    vectorizer: TfidfVectorizer,
    sc_matrix: np.ndarray,
) -> tuple[dict | None, float, dict]:
    """Find best SC match using TF-IDF + containment scoring.

    Returns (best_sc_track, final_score, debug_info).
    """
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
        score, score_debug = containment_score_with_penalty(
            local_tokens, critical_tokens, sc_tokens, sc_real_tokens,
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

    penalty_str = f"crit_pen={cp:.1f} noise_pen={np_:.2f} rev_remix_pen={rrp:.1f}"
    lines = [
        f"  [{score:.3f}] base={base:.3f} {penalty_str}",
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
# V1 scoring (for comparison) — same as original but without fixes
# ---------------------------------------------------------------------------

def tokenize_v1(text: str) -> set[str]:
    """Original v1 tokenizer — no synonym normalization, no underscore splitting."""
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
    """Original v1 stem cleaner — no underscore split, no album prefix strip."""
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
    """Original v1 scoring — no reverse remix penalty."""
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
    """Compute v1 score for a given local track + SC track pair."""
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

    # --- Build TF-IDF index once ---
    print("\nBuilding TF-IDF index over SC tracks...")
    vectorizer, sc_matrix = build_tfidf_index(sc_tracks)
    print(f"Index built. Matrix shape: {sc_matrix.shape}")

    # --- Match ---
    print("\nMatching local tracks → SC...")
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
    print("CONFIDENCE DISTRIBUTION")
    print("=" * 60)
    for b in BUCKET_KEYS:
        n = counts[b]
        pct = n / total * 100
        bar = "#" * int(pct / 2)
        print(f"  {b:>10}: {n:>5} ({pct:5.1f}%)  {bar}")

    print("\n" + "=" * 60)
    print("CUMULATIVE COUNTS")
    print("=" * 60)
    for threshold, label in [(0.90, ">=0.90"), (0.80, ">=0.80"), (0.70, ">=0.70"), (0.50, ">=0.50")]:
        cum = sum(1 for _, _, score, _ in results if score >= threshold)
        print(f"  {label}: {cum:>5} ({cum / total * 100:.1f}%)")

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
                # Compute v1 score for comparison
                v1_s = score_v1(lt, sc) if sc else 0.0
                spot_results[key] = (lt, sc, score, v1_s, debug)
                found = True
                break
        if not found:
            print("    NOT FOUND in local unlinked tracks")
            spot_results[key] = (None, None, 0.0, 0.0, {})

    # --- COMPARISON: v1 vs v2 ---
    print(f"\n{'=' * 60}")
    print("COMPARISON: v1 vs v2 scores")
    print("=" * 60)
    print(f"  {'Track':<45} {'v1':>6}  {'v2':>6}  {'delta':>7}")
    print(f"  {'-'*45} {'-'*6}  {'-'*6}  {'-'*7}")

    for title_frag, artist_frag, note in spot_checks:
        key = f"{title_frag}|{artist_frag or ''}"
        lt, sc, v2_s, v1_s, _ = spot_results.get(key, (None, None, 0.0, 0.0, {}))
        label = f"{title_frag}" + (f" ({artist_frag})" if artist_frag else "")
        delta = v2_s - v1_s
        delta_str = f"{delta:+.3f}"
        print(f"  {label:<45} {v1_s:>6.3f}  {v2_s:>6.3f}  {delta_str:>7}")


if __name__ == "__main__":
    main()
