"""Strategy 2: Title-focused matching.

Key insight: SC 'artist' field is often wrong (label/reposter like "Barong Family",
"Trap Sounds"). Match primarily on TITLE, use artist only as secondary signal.

Scoring:
  score = title_token_overlap * 0.8 + artist_token_overlap * 0.2

Where:
  title_token_overlap = |title_intersection| / |title_union| (Jaccard)
  artist_token_overlap = |artist_intersection| / |artist_union| (Jaccard)
    (local artist vs SC artist AND vs extracted SC title-artist prefix, take max)
"""

import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

DB_PATH = Path.home() / ".local/share/music-minion/music_minion.db"

NOISE_WORDS = {
    "free", "download", "dl", "official", "full", "stream",
    "original", "mix", "audio", "premiere", "exclusive", "out", "now",
}

# Punctuation stripper (keep alphanumerics + spaces)
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
# Collapse whitespace
_WS_RE = re.compile(r"\s+")

# Filename prefix patterns to strip
_DATE_PREFIX_RE = re.compile(r"^[A-Za-z]{3,9}\s+\d{2}_\s*")   # "Nov 23_ "
_NUM_PREFIX_RE  = re.compile(r"^\d+\s*[-–]\s*")                 # "01 - "


def clean_text(text: str) -> str:
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def tokenize(text: str) -> set[str]:
    tokens = set(clean_text(text).split())
    return tokens - NOISE_WORDS - {""}


def clean_filename_stem(path: str) -> str:
    stem = Path(path).stem
    stem = _DATE_PREFIX_RE.sub("", stem)
    stem = _NUM_PREFIX_RE.sub("", stem)
    return stem


def local_title_tokens(track: dict) -> set[str]:
    """Title tokens from DB title + cleaned filename stem."""
    parts = []
    title = track.get("title") or ""
    if title:
        parts.append(title)
    path = track.get("local_path") or ""
    if path:
        parts.append(clean_filename_stem(path))
    return tokenize(" ".join(parts))


def local_artist_tokens(track: dict) -> set[str]:
    artist = track.get("artist") or ""
    return tokenize(artist)


# ---------------------------------------------------------------------------
# SC title parsing
# ---------------------------------------------------------------------------

def split_sc_title(sc_title: str) -> tuple[str, str]:
    """Split 'Artist - Title [extras]' into (artist_part, title_part).

    Returns (artist_part, title_part). If no ' - ' separator found, returns
    ("", sc_title).  Takes the LAST segment as title to handle
    'A - B - Title' patterns.
    """
    parts = sc_title.split(" - ", maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", sc_title.strip()


def sc_title_tokens(sc_track: dict) -> set[str]:
    """Tokens from the 'real title' portion of SC title (after splitting on ' - ')."""
    raw = sc_track.get("title") or ""
    _, title_part = split_sc_title(raw)
    return tokenize(title_part)


def sc_full_title_tokens(sc_track: dict) -> set[str]:
    """Tokens from the full SC title (unmodified)."""
    return tokenize(sc_track.get("title") or "")


def sc_artist_tokens(sc_track: dict) -> set[str]:
    """Tokens from SC artist field."""
    return tokenize(sc_track.get("artist") or "")


def sc_extracted_artist_tokens(sc_track: dict) -> set[str]:
    """Tokens from the artist prefix extracted from SC title."""
    raw = sc_track.get("title") or ""
    artist_part, _ = split_sc_title(raw)
    return tokenize(artist_part)


# ---------------------------------------------------------------------------
# Jaccard
# ---------------------------------------------------------------------------

def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


# ---------------------------------------------------------------------------
# Main score function
# ---------------------------------------------------------------------------

def score_pair(local: dict, sc: dict) -> float:
    """Score a (local, SC) pair using title-focused strategy."""
    lt_tokens = local_title_tokens(local)
    la_tokens = local_artist_tokens(local)

    # SC title tokens: try split-title first, also try full title
    sct_split = sc_title_tokens(sc)
    sct_full  = sc_full_title_tokens(sc)

    # Use whichever gives higher title overlap
    title_score = max(
        jaccard(lt_tokens, sct_split),
        jaccard(lt_tokens, sct_full),
    )

    # Artist: compare local artist vs SC artist field AND vs extracted SC-title artist
    sc_art = sc_artist_tokens(sc)
    sc_ext_art = sc_extracted_artist_tokens(sc)
    artist_score = max(
        jaccard(la_tokens, sc_art),
        jaccard(la_tokens, sc_ext_art),
    )

    return 0.8 * title_score + 0.2 * artist_score


# ---------------------------------------------------------------------------
# DB fetch
# ---------------------------------------------------------------------------

def fetch_tracks(conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
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
    return [dict(r) for r in local_rows], [dict(r) for r in sc_rows]


# ---------------------------------------------------------------------------
# Bucketing helpers
# ---------------------------------------------------------------------------

BUCKET_LABELS = ["0.90+", "0.80-0.89", "0.70-0.79", "0.60-0.69", "0.50-0.59", "< 0.50"]


def bucket_for(score: float) -> str:
    if score >= 0.90:
        return "0.90+"
    elif score >= 0.80:
        return "0.80-0.89"
    elif score >= 0.70:
        return "0.70-0.79"
    elif score >= 0.60:
        return "0.60-0.69"
    elif score >= 0.50:
        return "0.50-0.59"
    else:
        return "< 0.50"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_matching() -> None:
    conn = sqlite3.connect(DB_PATH)
    local_tracks, sc_tracks = fetch_tracks(conn)
    conn.close()

    print(f"Local unlinked: {len(local_tracks)}")
    print(f"SC tracks in DB: {len(sc_tracks)}")
    print()

    # Pre-compute SC token sets for speed
    print("Pre-tokenizing SC tracks...")
    sc_precomputed: list[tuple[dict, set[str], set[str], set[str], set[str]]] = []
    for sc in sc_tracks:
        sc_precomputed.append((
            sc,
            sc_title_tokens(sc),
            sc_full_title_tokens(sc),
            sc_artist_tokens(sc),
            sc_extracted_artist_tokens(sc),
        ))

    # Match
    print("Matching (this may take several minutes)...")
    results: list[tuple[dict, dict | None, float]] = []
    report_interval = max(1, len(local_tracks) // 20)

    for i, lt in enumerate(local_tracks):
        if i % report_interval == 0:
            pct = i / len(local_tracks) * 100
            print(f"  {i}/{len(local_tracks)} ({pct:.0f}%)")

        lt_tokens = local_title_tokens(lt)
        la_tokens = local_artist_tokens(lt)

        if not lt_tokens:
            results.append((lt, None, 0.0))
            continue

        best_match: dict | None = None
        best_score = 0.0

        for sc, sct_split, sct_full, sc_art, sc_ext_art in sc_precomputed:
            title_score = max(
                jaccard(lt_tokens, sct_split),
                jaccard(lt_tokens, sct_full),
            )
            artist_score = max(
                jaccard(la_tokens, sc_art),
                jaccard(la_tokens, sc_ext_art),
            )
            score = 0.8 * title_score + 0.2 * artist_score

            if score > best_score:
                best_score = score
                best_match = sc

        results.append((lt, best_match, best_score))

    print(f"Done. Total: {len(results)}\n")

    # Bucket results
    counts: Counter = Counter()
    by_bucket: dict[str, list] = {b: [] for b in BUCKET_LABELS}

    for lt, match, score in results:
        b = bucket_for(score)
        counts[b] += 1
        by_bucket[b].append((lt, match, score))

    total = len(results)

    print("=== CONFIDENCE DISTRIBUTION ===")
    for b in BUCKET_LABELS:
        n = counts[b]
        pct = n / total * 100 if total else 0
        bar = "#" * int(pct / 2)
        print(f"  {b:>10}: {n:>5} ({pct:5.1f}%) {bar}")

    # Cumulative
    c90 = counts["0.90+"]
    c80 = c90 + counts["0.80-0.89"]
    c70 = c80 + counts["0.70-0.79"]
    c50 = c70 + counts["0.60-0.69"] + counts["0.50-0.59"]
    print(f"\n  >= 0.90: {c90:>5} ({c90/total*100:.1f}%)")
    print(f"  >= 0.80: {c80:>5} ({c80/total*100:.1f}%)")
    print(f"  >= 0.70: {c70:>5} ({c70/total*100:.1f}%)")
    print(f"  >= 0.50: {c50:>5} ({c50/total*100:.1f}%)")

    # Sample display
    def show(bucket_name: str, n: int = 10) -> None:
        items = by_bucket[bucket_name]
        print(f"\n=== {bucket_name} — {len(items)} total, showing {min(n, len(items))} ===")
        for lt, match, score in items[:n]:
            local_label = f"{lt.get('artist') or '?'} - {lt.get('title') or '?'}"
            sc_label = f"{match['artist']} - {match['title']}" if match else "NO MATCH"
            lt_toks = local_title_tokens(lt)
            la_toks = local_artist_tokens(lt)
            if match:
                sct_split = sc_title_tokens(match)
                sct_full  = sc_full_title_tokens(match)
                sc_art    = sc_artist_tokens(match)
                sc_ext    = sc_extracted_artist_tokens(match)
                t_score = max(jaccard(lt_toks, sct_split), jaccard(lt_toks, sct_full))
                a_score = max(jaccard(la_toks, sc_art), jaccard(la_toks, sc_ext))
                print(f"  [{score:.3f} t={t_score:.2f} a={a_score:.2f}]  {local_label}")
                print(f"                              {sc_label}")
            else:
                print(f"  [{score:.3f}]  {local_label}")
                print(f"           NO MATCH")

    for b in BUCKET_LABELS:
        show(b, 10)

    # Spot checks
    print("\n=== SPOT CHECKS ===")
    spot_checks = [
        ("LRAD",                        None),
        ("Nap In The Club",             None),         # Two Owls Remix
        ("#SELFIE",                     None),
        ("Hawt",                        "Brillz"),
        ("The Game",                    "Curfew"),
        ("Boss Mode",                   "Knife Party"),
        ("Vincent",                     None),          # Vincent - Only
    ]

    for title_frag, artist_frag in spot_checks:
        hits = [
            (lt, match, score)
            for lt, match, score in results
            if title_frag.lower() in (lt.get("title") or "").lower()
            and (artist_frag is None or artist_frag.lower() in (lt.get("artist") or "").lower())
        ]
        if not hits:
            print(f"\n  [NOT FOUND] '{title_frag}'" + (f" by {artist_frag}" if artist_frag else ""))
            continue
        # Show all local tracks matching the fragment
        for lt, match, score in hits:
            local_label = f"{lt.get('artist') or '?'} - {lt.get('title') or '?'}"
            sc_label = f"{match['artist']} - {match['title']}" if match else "NO MATCH"
            lt_toks = local_title_tokens(lt)
            la_toks = local_artist_tokens(lt)
            if match:
                sct_split = sc_title_tokens(match)
                sct_full  = sc_full_title_tokens(match)
                sc_art    = sc_artist_tokens(match)
                sc_ext    = sc_extracted_artist_tokens(match)
                t_score = max(jaccard(lt_toks, sct_split), jaccard(lt_toks, sct_full))
                a_score = max(jaccard(la_toks, sc_art), jaccard(la_toks, sc_ext))
                print(f"\n  [{score:.3f} t={t_score:.2f} a={a_score:.2f}]  LOCAL: {local_label}")
                print(f"                              SC:    {sc_label}")
            else:
                print(f"\n  [{score:.3f}]  LOCAL: {local_label}")
                print(f"             SC:    NO MATCH")


if __name__ == "__main__":
    run_matching()
