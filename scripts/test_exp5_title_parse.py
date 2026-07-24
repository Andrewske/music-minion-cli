"""Experiment 5: Enhanced SC Title Parsing + Artist Extraction

Improvement over merged_v2:
- parse_sc_title_enhanced() returns structured {real_title, extracted_artists, all_text}
- Parsing rules:
  a. Strip bracket suffixes first
  b. 2+ dashes: "A - B - C" → extracted_artists=["A","B"], real_title="C"
  c. 1 dash: "A - B" → extracted_artists=["A"], real_title="B"
  d. No dash + label-looking SC artist → treat first cap word(s) of title as artist
  e. Normalize "x" between capitalized words as collaboration indicator
- SC token set = union(full_title, real_title, extracted_artists, sc_artist_field)
- Scoring logic unchanged

Run with: uv run python scripts/test_exp5_title_parse.py
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

# Label suffix words — if SC artist field ends with these, it's likely a label/reposter
LABEL_SUFFIXES = {
    "records", "music", "family", "sounds", "audio", "collective", "label",
    "recordings", "entertainment", "media", "agency", "group", "digital",
    "worldwide", "international", "official", "hq",
}

# Pattern: "x" between capitalized words = collab indicator
COLLAB_X_RE = re.compile(r"\b([A-Z][a-zA-Z0-9]*)\s+x\s+([A-Z][a-zA-Z0-9]*)\b")

# Bracket/paren noise at end of real title (not free-download — those are already stripped)
BRACKET_NOISE_RE = re.compile(r"\s*[\[\(][^\]\)]*[\]\)]$")


# ---------------------------------------------------------------------------
# Normalization helpers  (unchanged from merged_v2)
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


# ---------------------------------------------------------------------------
# Synonym normalization  (unchanged from merged_v2)
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
# Enhanced SC title parser  (NEW in exp5)
# ---------------------------------------------------------------------------

def _looks_like_label(sc_artist: str) -> bool:
    """Return True if SC artist field appears to be a label/reposter name."""
    if not sc_artist:
        return False
    lower = sc_artist.lower().strip()
    # Ends with a label suffix word
    for suffix in LABEL_SUFFIXES:
        if lower.endswith(suffix) or lower.endswith(" " + suffix):
            return True
    # Contains "records" / "music" anywhere
    if re.search(r"\b(?:records|music|sounds|collective)\b", lower):
        return True
    return False


def _extract_collab_artists(text: str) -> list[str]:
    """Find 'ArtistA x ArtistB' patterns and return both names."""
    artists: list[str] = []
    for m in COLLAB_X_RE.finditer(text):
        artists.append(m.group(1))
        artists.append(m.group(2))
    return artists


def parse_sc_title_enhanced(sc_title: str, sc_artist: str) -> dict:
    """Parse SC title into structured components.

    Returns:
        real_title: str — the actual track title (last dash segment)
        extracted_artists: list[str] — artist names found in the title string
        all_text: str — combined text for tokenization (real_title + extracted_artists + sc_artist)
    """
    # Step 1: strip bracket noise suffixes
    cleaned = strip_bracket_suffixes(sc_title)

    # Step 2: expand "A x B" collabs before splitting (preserve for artist list)
    collab_artists = _extract_collab_artists(cleaned)

    # Step 3: split on " - "
    segments = [s.strip() for s in cleaned.split(" - ") if s.strip()]

    extracted_artists: list[str] = list(collab_artists)
    real_title: str

    if len(segments) >= 3:
        # "A - B - C" or "Label - Artist - Title"
        # Last segment = real title; all preceding segments = potential artists
        real_title = segments[-1]
        for seg in segments[:-1]:
            extracted_artists.append(seg)
    elif len(segments) == 2:
        # "A - B" → A = artist, B = title
        extracted_artists.append(segments[0])
        real_title = segments[1]
    elif segments:
        # No dash — check if SC artist looks like a label
        real_title = segments[0]
        if _looks_like_label(sc_artist):
            # Try to pull first capitalized word(s) from title as artist
            cap_match = re.match(r"^([A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*)*)\s+", real_title)
            if cap_match:
                extracted_artists.append(cap_match.group(1))
    else:
        real_title = cleaned

    # Step 4: clean trailing bracket noise from real_title (e.g. "(Original Mix)")
    real_title = BRACKET_NOISE_RE.sub("", real_title).strip()

    # Step 5: build all_text = real_title + extracted_artists + sc_artist_field
    all_parts = [real_title] + extracted_artists + ([sc_artist] if sc_artist else [])
    all_text = " ".join(all_parts)

    return {
        "real_title": real_title,
        "extracted_artists": extracted_artists,
        "all_text": all_text,
    }


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
    """Build SC token set using enhanced parsing.

    Returns (all_tokens, real_title_tokens).
    all_tokens now includes extracted_artists from the SC title structure.
    """
    title = track.get("title") or ""
    artist = track.get("artist") or ""

    parsed = parse_sc_title_enhanced(title, artist)

    # Real-title tokens: just the parsed real title + sc_artist
    real_tokens = tokenize(f"{parsed['real_title']} {artist}")

    # Enhanced all_tokens: real_title + extracted_artists + sc_artist + full_original_title
    # Full original title is kept for fallback signal
    full_original_tokens = tokenize(f"{title} {artist}")
    enhanced_tokens = tokenize(parsed["all_text"]) | full_original_tokens

    return enhanced_tokens, real_tokens


def has_remix_indicators(tokens: set[str]) -> bool:
    non_vip_remix = REMIX_INDICATORS - {"vip"}
    return bool(tokens & non_vip_remix)


# ---------------------------------------------------------------------------
# TF-IDF index  (updated to use enhanced parsing in index)
# ---------------------------------------------------------------------------

def build_tfidf_index(sc_tracks: list[dict]) -> tuple[TfidfVectorizer, np.ndarray]:
    strings = []
    for t in sc_tracks:
        artist = t.get("artist", "") or ""
        title = t.get("title", "") or ""
        parsed = parse_sc_title_enhanced(title, artist)
        # Use enhanced all_text for richer index
        combined = normalize_text(f"{artist} {title} {parsed['all_text']}")
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
# Containment scoring  (unchanged logic from merged_v2)
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
    sc_has_remix = has_remix_indicators(used_sc_tokens) or has_remix_indicators(sc_tokens)
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
# Main matching
# ---------------------------------------------------------------------------

def match_track(
    local_track: dict,
    sc_tracks: list[dict],
    vectorizer: TfidfVectorizer,
    sc_matrix: np.ndarray,
) -> tuple[dict | None, float, dict]:
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
# Baseline v2 scoring (for delta comparison)
# ---------------------------------------------------------------------------

def parse_sc_real_title_v2(sc_title: str) -> str:
    cleaned = strip_bracket_suffixes(sc_title)
    if " - " in cleaned:
        return cleaned.split(" - ")[-1].strip()
    return cleaned


def sc_track_tokens_v2(track: dict) -> tuple[set[str], set[str]]:
    title = track.get("title") or ""
    artist = track.get("artist") or ""
    full_tokens = tokenize(f"{title} {artist}")
    real_title = parse_sc_real_title_v2(title)
    real_tokens = tokenize(f"{real_title} {artist}")
    return full_tokens | real_tokens, real_tokens


def score_v2_baseline(local_track: dict, sc: dict) -> float:
    """Compute merged_v2 score for a given local+SC pair (for delta)."""
    if sc is None:
        return 0.0
    local_tokens, critical_tokens = local_track_tokens(local_track)
    sc_tokens, sc_real_tokens = sc_track_tokens_v2(sc)
    score, _ = containment_score_with_penalty(
        local_tokens, critical_tokens, sc_tokens, sc_real_tokens,
    )
    return score


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

    print("\nBuilding TF-IDF index over SC tracks (enhanced)...")
    vectorizer, sc_matrix = build_tfidf_index(sc_tracks)
    print(f"Index built. Matrix shape: {sc_matrix.shape}")

    print("\nMatching local tracks → SC (exp5: enhanced title parse)...")
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
    print("CONFIDENCE DISTRIBUTION  [exp5: enhanced title parse]")
    print("=" * 60)
    for b in BUCKET_KEYS:
        n = counts[b]
        pct = n / total * 100
        bar = "#" * int(pct / 2)
        print(f"  {b:>10}: {n:>5} ({pct:5.1f}%)  {bar}")

    print("\n" + "=" * 60)
    print("CUMULATIVE COUNTS")
    print("=" * 60)
    BASELINE = {0.90: 71.3, 0.80: 76.3, 0.70: 80.0, 0.50: 85.0}
    for threshold, label in [(0.90, ">=0.90"), (0.80, ">=0.80"), (0.70, ">=0.70"), (0.50, ">=0.50")]:
        cum = sum(1 for _, _, score, _ in results if score >= threshold)
        pct = cum / total * 100
        base_pct = BASELINE.get(threshold, 0.0)
        delta = pct - base_pct
        delta_str = f"({delta:+.1f}pp vs baseline)" if base_pct else ""
        print(f"  {label}: {cum:>5} ({pct:.1f}%)  {delta_str}")

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
                v2_s = score_v2_baseline(lt, sc)
                spot_results[key] = (lt, sc, score, v2_s, debug)
                found = True
                break
        if not found:
            print("    NOT FOUND in local unlinked tracks")
            spot_results[key] = (None, None, 0.0, 0.0, {})

    # --- COMPARISON: v2 baseline vs exp5 ---
    print(f"\n{'=' * 60}")
    print("COMPARISON: merged_v2 baseline vs exp5 (enhanced title parse)")
    print("=" * 60)
    print(f"  {'Track':<45} {'v2_base':>8}  {'exp5':>6}  {'delta':>7}")
    print(f"  {'-'*45} {'-'*8}  {'-'*6}  {'-'*7}")

    for title_frag, artist_frag, note in spot_checks:
        key = f"{title_frag}|{artist_frag or ''}"
        lt, sc, exp5_s, v2_s, _ = spot_results.get(key, (None, None, 0.0, 0.0, {}))
        label = f"{title_frag}" + (f" ({artist_frag})" if artist_frag else "")
        delta = exp5_s - v2_s
        delta_str = f"{delta:+.3f}"
        print(f"  {label:<45} {v2_s:>8.3f}  {exp5_s:>6.3f}  {delta_str:>7}")

    # --- Enhanced parsing spot checks ---
    print(f"\n{'=' * 60}")
    print("ENHANCED PARSE EXAMPLES (parse_sc_title_enhanced demo)")
    print("=" * 60)
    demo_cases = [
        ("Caspa & Rusko - Cockney Thug - 50 Calibre Remix", "Hospital Records"),
        ("Skrillex & Diplo - Where Are U Now", "Jack U"),
        ("Artist x Artist2 - Track Name", "Label Records"),
        ("Just A Track Name With No Dash", "XYZ Music"),
        ("Flume - Never Be Like You feat. Kai", "Future Classic"),
        ("LRAD (Culprate Remix)", "Knife Party"),
        ("Chase & Status - No Problem ft. Professor Green", "Chase & Status"),
    ]
    for title, artist in demo_cases:
        parsed = parse_sc_title_enhanced(title, artist)
        print(f"\n  title:   {title!r}")
        print(f"  artist:  {artist!r}")
        print(f"  → real_title:        {parsed['real_title']!r}")
        print(f"  → extracted_artists: {parsed['extracted_artists']}")
        print(f"  → all_text:          {parsed['all_text']!r}")


if __name__ == "__main__":
    main()
