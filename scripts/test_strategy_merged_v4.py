"""Strategy Merged v4: v3 + EXP8 (filename-as-ground-truth scoring).

Base: Merged v3 (artist-weight + guarded substring + guarded lev)

Added from EXP8:
- Separate filename scoring path: cleaned filename stem scored independently
  against SC tracks using containment + substring matching
- Filename substring boost: if cleaned filename is substring of SC title
  (or vice versa), high confidence — requires >=2 meaningful words
- Final score = max(v3_score, filename_score) — whichever path wins

Key insight: local files were downloaded from SoundCloud, so filenames preserve
the ORIGINAL SC title before Kevin cleaned up metadata. Filenames like
"Knife Party - Boss Mode [Free Download].mp3" contain the exact SC title.

Run with: uv run python scripts/test_strategy_merged_v4.py
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
# Artist-weighted containment scoring (from v3/EXP3)
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
# Substring boost (from v3/EXP1)
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
# Levenshtein boost (from v3/EXP4)
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
                "fn_tokens": filename_tokens,
                "fn_cleaned": cleaned_stem,
                "fn_tfidf": tfidf_s,
            }

    return best_match, best_score, best_debug


# ---------------------------------------------------------------------------
# Main matching
# ---------------------------------------------------------------------------

def match_track(
    local_track: dict,
    sc_tracks: list[dict],
    vectorizer: TfidfVectorizer,
    sc_matrix: np.ndarray,
) -> tuple[dict | None, float, dict]:
    local_tokens, critical_tokens, local_artist_tokens = local_track_tokens(local_track)
    local_title_norm = normalize_for_substring(local_track.get("title") or "")

    candidates = tfidf_top_k(local_track, vectorizer, sc_matrix, k=10)
    if not candidates:
        return None, 0.0, {}

    # --- V3 path: title+artist+filename combined ---
    best_v3_match = None
    best_v3_score = 0.0
    best_v3_debug: dict = {}

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
            best_v3_debug = {
                "tfidf": tfidf_s,
                "containment": containment_s,
                "substr_boosted": was_substr_boosted,
                "lev_score": lev_score,
                "lev_boosted": final_score > score_after_substr,
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
                "non_artist_coverage": score_debug["non_artist_coverage"],
                "missing_critical": score_debug["missing_critical"],
                "artist_matched": score_debug["artist_matched"],
                "artist_missed": score_debug["artist_missed"],
            }

    # --- EXP8: Filename path (reuses same TF-IDF candidates) ---
    fn_match, fn_score, fn_debug = score_filename_path(
        local_track, sc_tracks, candidates,
    )

    if fn_score > best_v3_score:
        merged_debug = {**fn_debug, "path_winner": "filename", "v3_score": best_v3_score}
        return fn_match, fn_score, merged_debug

    merged_debug = {**best_v3_debug, "path_winner": "v3", "fn_score": fn_score}
    return best_v3_match, best_v3_score, merged_debug


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
    path_winner = debug.get("path_winner", "v3")

    if path_winner == "filename":
        fn_tokens = debug.get("fn_tokens", set())
        fn_cleaned = debug.get("fn_cleaned", "")
        fn_cont = debug.get("fn_containment", 0.0)
        fn_substr = debug.get("fn_substr_boosted", False)
        v3_score = debug.get("v3_score", 0.0)

        local_label = f"{lt.get('artist') or '?'} - {lt.get('title') or '?'}"
        sc_label = f"{sc['artist']} - {sc['title']}" if sc else "NO MATCH"
        boost_str = " [FN-SUBSTR]" if fn_substr else ""
        lines = [
            f"  [{score:.3f}] PATH=FILENAME fn_cont={fn_cont:.3f}{boost_str}  v3_was={v3_score:.3f}",
            f"    LOCAL: {local_label}",
            f"    SC:    {sc_label}",
            f"    fn_cleaned={fn_cleaned!r}",
            f"    fn_tokens={sorted(fn_tokens)}",
        ]
        return "\n".join(lines)

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
    sb = debug.get("substr_boosted", False)
    lb = debug.get("lev_boosted", False)
    cont = debug.get("containment", score)
    fn_score = debug.get("fn_score", 0.0)

    penalty_str = f"crit={cp:.1f} noise={np_:.2f} rrp={rrp:.1f} ab={ab:.1f}"
    boost_parts = []
    if sb:
        boost_parts.append("SUBSTR")
    if lb:
        boost_parts.append(f"LEV={debug.get('lev_score', 0):.2f}")
    boost_str = f" [{'+'.join(boost_parts)} cont={cont:.3f}]" if boost_parts else ""
    fn_str = f"  fn={fn_score:.3f}" if fn_score > 0 else ""

    lines = [
        f"  [{score:.3f}] PATH=V3 base={base:.3f} {penalty_str}{boost_str}{fn_str}",
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
# Baseline v3 scoring for comparison
# ---------------------------------------------------------------------------

def score_v3(local_track: dict, sc: dict) -> float:
    title = local_track.get("title") or ""
    artist = local_track.get("artist") or ""
    path = local_track.get("local_path", "")
    parts = [p for p in [title, artist] if p]
    if path:
        parts.append(clean_filename_stem(Path(path).stem))
    local_tokens = tokenize(" ".join(parts))
    critical = get_critical_tokens(title, artist)

    sc_title = sc.get("title") or ""
    sc_artist = sc.get("artist") or ""
    sc_full = tokenize(f"{sc_title} {sc_artist}")
    sc_real = tokenize(f"{parse_sc_real_title(sc_title)} {sc_artist}")
    sc_all = sc_full | sc_real

    if not local_tokens:
        return 0.0

    int_full = local_tokens & sc_all
    int_real = local_tokens & sc_real
    if len(int_real) >= len(int_full):
        intersection = int_real
        used = sc_real
    else:
        intersection = int_full
        used = sc_all

    base = len(intersection) / len(local_tokens)
    cp = 1.0
    actual_crit = critical - REMIX_INDICATORS - FEAT_INDICATORS
    if actual_crit and (actual_crit - used):
        cp = 0.5
    np_ = 0.85 if len(used) > 2.5 * len(local_tokens) else 1.0
    rrp = 1.0
    if (has_remix_indicators(used) or has_remix_indicators(sc_all)) and not has_remix_indicators(local_tokens):
        rrp = 0.5
    return base * cp * np_ * rrp


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

    print("\nBuilding TF-IDF index...")
    vectorizer, sc_matrix = build_tfidf_index(sc_tracks)
    print(f"Index built. Shape: {sc_matrix.shape}")

    print("\nMatching (v4: v3 + filename-as-ground-truth)...")
    results: list[tuple[dict, dict | None, float, dict]] = []
    substr_count = 0
    lev_count = 0
    fn_path_count = 0
    fn_substr_count = 0

    for i, lt in enumerate(local_tracks):
        if i > 0 and i % 500 == 0:
            print(f"  {i:>5}/{len(local_tracks)} ({i / len(local_tracks) * 100:.0f}%)")

        best_sc, score, debug = match_track(lt, sc_tracks, vectorizer, sc_matrix)
        results.append((lt, best_sc, score, debug))
        if debug.get("path_winner") == "filename":
            fn_path_count += 1
            if debug.get("fn_substr_boosted"):
                fn_substr_count += 1
        else:
            if debug.get("substr_boosted"):
                substr_count += 1
            if debug.get("lev_boosted"):
                lev_count += 1

    total = len(results)
    print(f"  {total}/{total} (100%) — done")
    print(f"  Path=FILENAME wins : {fn_path_count} ({fn_path_count / total * 100:.1f}%)")
    print(f"    of which fn-substr: {fn_substr_count} ({fn_substr_count / total * 100:.1f}%)")
    print(f"  Path=V3 wins       : {total - fn_path_count} ({(total - fn_path_count) / total * 100:.1f}%)")
    print(f"    substr boosts    : {substr_count} ({substr_count / total * 100:.1f}%)")
    print(f"    lev boosts       : {lev_count} ({lev_count / total * 100:.1f}%)")

    # --- Bucket distribution ---
    by_bucket: dict[str, list] = {k: [] for k in BUCKET_KEYS}
    counts: Counter = Counter()

    for lt, sc, score, debug in results:
        b = bucket_for(score)
        by_bucket[b].append((lt, sc, score, debug))
        counts[b] += 1

    print("\n" + "=" * 60)
    print("CONFIDENCE DISTRIBUTION  [MERGED V4]")
    print("=" * 60)
    for b in BUCKET_KEYS:
        n = counts[b]
        pct = n / total * 100
        bar = "#" * int(pct / 2)
        fn_in_bucket = sum(
            1 for lt, sc, score, debug in by_bucket[b]
            if debug.get("path_winner") == "filename"
        )
        fn_tag = f"  [fn={fn_in_bucket}]" if fn_in_bucket else ""
        print(f"  {b:>10}: {n:>5} ({pct:5.1f}%)  {bar}{fn_tag}")

    print("\n" + "=" * 60)
    print("CUMULATIVE COUNTS")
    print("=" * 60)
    baseline = {0.90: 77.0, 0.80: 79.7}
    for threshold, label in [(0.90, ">=0.90"), (0.80, ">=0.80"), (0.70, ">=0.70"), (0.50, ">=0.50")]:
        cum = sum(1 for _, _, score, _ in results if score >= threshold)
        pct = cum / total * 100
        bl = baseline.get(threshold)
        delta_str = f"  (v3: {bl:.1f}%, delta {pct - bl:+.1f}%)" if bl else ""
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
    show_bucket("0.60-0.69", 10)
    show_bucket("0.50-0.59", 10)
    show_bucket("< 0.50", 10)

    # --- Filename path winners ---
    fn_wins = [
        (lt, sc, score, debug)
        for lt, sc, score, debug in results
        if debug.get("path_winner") == "filename"
    ]
    fn_wins_sorted = sorted(fn_wins, key=lambda x: x[2], reverse=True)
    print(f"\n{'=' * 60}")
    print(f"FILENAME PATH WINNERS — {len(fn_wins)} total, showing top 20")
    print("=" * 60)
    for lt, sc, score, debug in fn_wins_sorted[:20]:
        path = lt.get("local_path", "")
        raw_stem = Path(path).stem if path else ""
        v3_score = debug.get("v3_score", 0.0)
        delta = score - v3_score
        fn_substr = "[FN-SUBSTR]" if debug.get("fn_substr_boosted") else ""
        local_label = f"{lt.get('artist') or '?'} - {lt.get('title') or '?'}"
        sc_label = f"{sc['artist']} - {sc['title']}" if sc else "NO MATCH"
        print(f"  [{score:.3f} vs v3={v3_score:.3f} delta={delta:+.3f}] {fn_substr}")
        print(f"    LOCAL:  {local_label}")
        print(f"    SC:     {sc_label}")
        print(f"    stem:   {raw_stem!r}")

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
        print(f"\n  >> '{title_frag}'" + (f" by '{artist_frag}'" if artist_frag else "") + (f"  [{note}]" if note else ""))
        found = False
        for lt, sc, score, debug in results:
            lt_title = (lt.get("title") or "").lower()
            lt_artist = (lt.get("artist") or "").lower()
            if title_frag.lower() in lt_title and (artist_frag is None or artist_frag.lower() in lt_artist):
                print(format_sample(lt, sc, score, debug))
                v3_baseline = debug.get("v3_score", score) if debug.get("path_winner") == "filename" else score
                spot_results[key] = (lt, sc, score, v3_baseline, debug)
                found = True
                break
        if not found:
            print("    NOT FOUND")
            spot_results[key] = (None, None, 0.0, 0.0, {})

    print(f"\n{'=' * 60}")
    print("COMPARISON: v3 baseline vs v4 merged")
    print("=" * 60)
    print(f"  {'Track':<45} {'v3':>6}  {'v4':>6}  {'delta':>7}  path/boosts")
    print(f"  {'-'*45} {'-'*6}  {'-'*6}  {'-'*7}  {'-'*12}")

    for title_frag, artist_frag, note in spot_checks:
        key = f"{title_frag}|{artist_frag or ''}"
        lt, sc, v4_s, v3_s, debug = spot_results.get(key, (None, None, 0.0, 0.0, {}))
        label = f"{title_frag}" + (f" ({artist_frag})" if artist_frag else "")
        delta = v4_s - v3_s
        path_winner = debug.get("path_winner", "v3")
        boosts = [path_winner.upper()]
        if path_winner == "filename":
            if debug.get("fn_substr_boosted"):
                boosts.append("fn-sub")
        else:
            if debug.get("substr_boosted"):
                boosts.append("sub")
            if debug.get("lev_boosted"):
                boosts.append("lev")
            if debug.get("artist_boost", 1.0) > 1.0:
                boosts.append("art")
        boost_str = "+".join(boosts)
        print(f"  {label:<45} {v3_s:>6.3f}  {v4_s:>6.3f}  {delta:>+7.3f}  {boost_str}")


if __name__ == "__main__":
    main()
