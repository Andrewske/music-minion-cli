"""Test script: Strategy 3 — Containment with Critical Token Penalties.

Key insight: A correct match means ALL important local tokens appear in SC.
Extra SC tokens (label names, "[Free Download]") are OK.
But MISSING tokens from local = likely wrong match.
"""

import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from music_minion.domain.library.deduplication import normalize_string

DB_PATH = Path.home() / ".local/share/music-minion/music_minion.db"

NOISE_TOKENS = {
    "free", "download", "dl", "official", "full", "stream",
    "original", "mix", "audio", "premiere", "exclusive",
    "single", "master", "explicit", "ep", "vol",
}

# Tokens that indicate version specificity (remix artist, feat artist follow these)
REMIX_INDICATORS = {"remix", "flip", "vip", "edit", "rework", "bootleg"}
FEAT_INDICATORS = {"feat", "ft", "featuring"}


def tokenize(text: str) -> list[str]:
    """Normalize and split into tokens (preserving order for critical extraction)."""
    normalized = normalize_string(text)
    return normalized.split()


def clean_tokens(tokens: list[str]) -> set[str]:
    """Remove noise tokens from a list."""
    return {t for t in tokens if t not in NOISE_TOKENS}


def extract_critical_tokens(tokens: list[str]) -> set[str]:
    """Extract tokens that indicate a specific version (remix artist, feat artist).

    Returns set of critical tokens (tokens AFTER remix/feat indicators).
    """
    critical: set[str] = set()
    for i, token in enumerate(tokens):
        if token in REMIX_INDICATORS or token in FEAT_INDICATORS:
            # Collect up to 2 tokens after the indicator as critical
            for j in range(i + 1, min(i + 3, len(tokens))):
                next_tok = tokens[j]
                if next_tok not in NOISE_TOKENS and next_tok not in REMIX_INDICATORS and next_tok not in FEAT_INDICATORS:
                    critical.add(next_tok)
    return critical


def build_local_token_data(track: dict) -> tuple[set[str], set[str]]:
    """Build (base_tokens, critical_tokens) from local track.

    Uses: title + artist + cleaned filename stem. NO album.
    Returns: (all_tokens, critical_tokens)
    """
    parts = []
    for field in ("title", "artist"):
        val = track.get(field)
        if val:
            parts.append(val)

    path = track.get("local_path", "")
    if path:
        stem = Path(path).stem
        # Strip "Nov 23_" style date prefixes
        stem = re.sub(r"^[A-Za-z]{3,9}\s+\d{2}_", "", stem)
        # Strip "01 - " track number prefixes
        stem = re.sub(r"^\d+\s*[-–]\s*", "", stem)
        parts.append(stem)

    all_tokens = []
    for part in parts:
        all_tokens.extend(tokenize(part))

    base_tokens = clean_tokens(all_tokens)
    critical_tokens = extract_critical_tokens(all_tokens)

    return base_tokens, critical_tokens


def build_sc_tokens(track: dict) -> set[str]:
    """Build token set from SC track (title + artist only)."""
    parts = []
    for field in ("title", "artist"):
        val = track.get(field)
        if val:
            parts.append(val)

    all_tokens = []
    for part in parts:
        all_tokens.extend(tokenize(part))

    return clean_tokens(all_tokens)


def containment_score(
    local_tokens: set[str],
    local_critical: set[str],
    sc_tokens: set[str],
) -> float:
    """Compute containment score with critical token penalty and noise penalty.

    base_score = |intersection| / |local_tokens|  (containment)
    critical_penalty: 0.5 if any critical local token missing from SC
    noise_penalty: 0.9 if |sc_tokens| > 2 * |local_tokens|
    final = base * critical_penalty * noise_penalty
    """
    if not local_tokens or not sc_tokens:
        return 0.0

    intersection = local_tokens & sc_tokens
    if not intersection:
        return 0.0

    base = len(intersection) / len(local_tokens)

    # Critical token penalty
    critical_penalty = 1.0
    if local_critical:
        missing_critical = local_critical - sc_tokens
        if missing_critical:
            critical_penalty = 0.5

    # Noise penalty: SC has way more tokens than local → likely wrong track
    noise_penalty = 1.0
    if len(sc_tokens) > 2 * len(local_tokens):
        noise_penalty = 0.9

    return base * critical_penalty * noise_penalty


def bucket_name(score: float) -> str:
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


def run_matching() -> None:
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

    print(f"Local unlinked: {len(local_tracks)}")
    print(f"SC tracks: {len(sc_tracks)}")

    # Pre-tokenize SC tracks
    print("Tokenizing SC tracks...")
    sc_token_sets = [(t, build_sc_tokens(t)) for t in sc_tracks]

    print("Matching...")
    results: list[tuple[dict, dict | None, float]] = []
    report_interval = max(1, len(local_tracks) // 20)

    for i, lt in enumerate(local_tracks):
        if i % report_interval == 0:
            pct = i / len(local_tracks) * 100
            print(f"  {i}/{len(local_tracks)} ({pct:.0f}%)")

        local_tokens, local_critical = build_local_token_data(lt)
        if not local_tokens:
            results.append((lt, None, 0.0))
            continue

        best_match: dict | None = None
        best_score = 0.0

        for sc_t, sc_tokens in sc_token_sets:
            score = containment_score(local_tokens, local_critical, sc_tokens)
            if score > best_score:
                best_score = score
                best_match = sc_t

        results.append((lt, best_match, best_score))

    # Bucket results
    bucket_names = ["0.90+", "0.80-0.89", "0.70-0.79", "0.60-0.69", "0.50-0.59", "< 0.50"]
    buckets: Counter = Counter()
    by_bucket: dict[str, list] = {b: [] for b in bucket_names}

    for lt, match, score in results:
        b = bucket_name(score)
        buckets[b] += 1
        by_bucket[b].append((lt, match, score))

    total = len(results)

    print("\n=== STRATEGY 3: CONTAINMENT WITH CRITICAL TOKEN PENALTIES ===")
    print(f"\n{'Bucket':>12}  {'Count':>6}  {'%':>6}  Bar")
    print("-" * 50)
    for b in bucket_names:
        count = buckets.get(b, 0)
        pct = count / total * 100
        bar = "#" * int(pct / 2)
        print(f"  {b:>10}: {count:>6} ({pct:5.1f}%) {bar}")

    # Cumulative counts
    print("\n=== CUMULATIVE COUNTS ===")
    cum_thresholds = [(">=0.90", 0.90), (">=0.80", 0.80), (">=0.70", 0.70), (">=0.50", 0.50)]
    for label, threshold in cum_thresholds:
        count = sum(1 for _, _, s in results if s >= threshold)
        pct = count / total * 100
        print(f"  {label}: {count:>6} / {total}  ({pct:.1f}%)")

    # Sample each bucket
    def show_samples(b: str, n: int = 10) -> None:
        items = by_bucket.get(b, [])
        print(f"\n=== {b} — {len(items)} total, showing {min(n, len(items))} samples ===")
        for lt, match, score in items[:n]:
            local_label = f"{lt.get('artist', '?')} - {lt.get('title', '?')}"
            sc_label = f"{match['artist']} - {match['title']}" if match else "NO MATCH"

            local_tokens, local_critical = build_local_token_data(lt)
            sc_tokens = build_sc_tokens(match) if match else set()
            shared = local_tokens & sc_tokens
            missing = local_tokens - sc_tokens
            extra = sc_tokens - local_tokens
            crit_miss = local_critical - sc_tokens if local_critical else set()

            print(f"  [{score:.3f}] LOCAL: {local_label}")
            print(f"           SC:    {sc_label}")
            print(f"           shared={sorted(shared)}  miss={sorted(missing)}  extra={sorted(extra)}", end="")
            if local_critical:
                print(f"  critical={sorted(local_critical)}  crit_miss={sorted(crit_miss)}", end="")
            print()

    for b in bucket_names:
        show_samples(b, 10)

    # Spot checks
    spot_checks = [
        ("LRAD", None),
        ("Nap In The Club", "Two Owls"),
        ("#SELFIE", None),
        ("Hawt", "Brillz"),
        ("The Game", "Curfew"),
        ("Boss Mode", "Knife Party"),
        ("Vincent", "Only"),
    ]

    print("\n=== SPOT CHECK ===")
    for title_frag, artist_frag in spot_checks:
        label = f'"{title_frag}"' + (f' by {artist_frag}' if artist_frag else "")
        found = False
        for lt, match, score in results:
            lt_title = (lt.get("title") or "").lower()
            lt_artist = (lt.get("artist") or "").lower()
            title_match = title_frag.lower() in lt_title
            artist_match = artist_frag is None or artist_frag.lower() in lt_artist
            if title_match and artist_match:
                local_label = f"{lt.get('artist', '?')} - {lt.get('title', '?')}"
                sc_label = f"{match['artist']} - {match['title']}" if match else "NO MATCH"
                local_tokens, local_critical = build_local_token_data(lt)
                sc_tokens = build_sc_tokens(match) if match else set()
                missing = local_tokens - sc_tokens
                crit_miss = local_critical - sc_tokens if local_critical else set()
                print(f"\n  Search: {label}")
                print(f"  [{score:.3f}] LOCAL: {local_label}")
                print(f"           SC:    {sc_label}")
                print(f"           missing={sorted(missing)}  critical={sorted(local_critical)}  crit_miss={sorted(crit_miss)}")
                found = True
                break
        if not found:
            print(f"\n  Search: {label}  → NOT FOUND IN LOCAL TRACKS")


if __name__ == "__main__":
    run_matching()
