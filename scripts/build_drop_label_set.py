#!/usr/bin/env python3
"""Pick ~50 un-cued tracks for drop labeling and write them as a Serato crate.

Selection: local tracks with a BPM and *no* Serato hot cues, spread across genre
families, plus deliberate hard cases flagged by the prototype detector:
  intro_loud    bass is already at full energy in the first 8 bars
  no_clear_drop weak loud-vs-quiet contrast anywhere (melodic / rolling tracks)
  double_drop   two separate drops score nearly the same

Label them in Serato with hot cue slot 4 on the first drop, then run:
    uv run python scripts/drop_detection_eval.py --drop-slot 4 --manifest <manifest.csv>

Usage:
    uv run python scripts/build_drop_label_set.py            # writes crate + manifest
    uv run python scripts/build_drop_label_set.py --dry-run  # just show the picks
"""

import argparse
import csv
import random
import sqlite3
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import NamedTuple

import numpy as np
from loguru import logger

import drop_detection_eval as dde

MANIFEST_PATH = Path.home() / ".local/share/music-minion/drop_label_set.csv"
CRATE_NAME = "Drop Labels"
SERATO_ROOT = Path.home() / "Music"  # same default as exporters.export_playlist
POOL_PER_FAMILY = 30  # tracks decoded per family to find hard cases
HARD_PER_KIND = 5
GENRE_FAMILIES = {
    "dubstep": ("dubstep", "riddim", "future dub", "tearout", "brostep", "space bass"),
    "trap": ("trap",),
    "dnb": ("drum & bass", "dnb", "jungle", "neuro", "liquid"),
    "house": ("house", "ukg", "garage", "bounce", "techno"),
    "midtempo": ("midtempo", "experimental", "wonk", "funk bass", "glitch"),
    "melodic": ("future bass", "melodic", "chill", "freeform", "electronic"),
}


class Candidate(NamedTuple):
    path: Path
    bpm: float
    genre: str
    family: str


class Profile(NamedTuple):
    candidate: Candidate
    kinds: tuple[str, ...]
    detected_s: float | None


def genre_family(genre: str) -> str:
    lowered = genre.lower()
    for family, needles in GENRE_FAMILIES.items():
        if any(n in lowered for n in needles):
            return family
    return "other"


def load_uncued(seed: int) -> list[Candidate]:
    """All local tracks with a BPM and no Serato cues, shuffled."""
    with sqlite3.connect(dde.DB_PATH) as conn:
        rows = conn.execute(
            "SELECT local_path, bpm, COALESCE(genre, '') FROM tracks "
            "WHERE local_path IS NOT NULL AND bpm > 0"
        ).fetchall()
    random.Random(seed).shuffle(rows)
    return [
        Candidate(Path(p), float(b), g, genre_family(g))
        for p, b, g in rows
        if Path(p).exists() and not dde.read_serato_cues(Path(p))
    ]


def build_pool(candidates: list[Candidate]) -> list[Candidate]:
    by_family: dict[str, list[Candidate]] = defaultdict(list)
    for c in candidates:
        if len(by_family[c.family]) < POOL_PER_FAMILY:
            by_family[c.family].append(c)
    return [c for group in by_family.values() for c in group]


def classify(beats: np.ndarray, scores: np.ndarray) -> tuple[str, ...]:
    """Hard-case flags from the per-beat bass energy and drop scores."""
    loud = np.percentile(beats, 90)
    kinds = []
    if beats[: dde.MIN_START_BEATS].mean() >= 0.65 * loud:
        kinds.append("intro_loud")
    if scores.max() < 1.0:
        kinds.append("no_clear_drop")
    peaks = dde.local_peaks(scores, radius=32)
    if (scores[peaks] >= 0.9 * scores.max()).sum() >= 2:
        kinds.append("double_drop")
    return tuple(kinds)


def profile(candidate: Candidate) -> Profile | None:
    try:
        env = dde.bass_envelope(dde.load_audio(candidate.path))
    except (dde.subprocess.CalledProcessError, ValueError) as e:
        logger.warning(f"Skipping {candidate.path}: {e}")
        return None
    fpb = (60.0 / dde.analysis_bpm(candidate.bpm)) * dde.SAMPLE_RATE / dde.HOP
    phase = dde.beat_phase(env, fpb)
    beats = dde.per_beat_energy(env, fpb, phase)
    scores = dde.drop_scores(beats)
    first, _, _ = dde.pick_drops(scores)
    detected = None if first is None else (phase + first * fpb) * dde.HOP / dde.SAMPLE_RATE
    return Profile(candidate, classify(beats, scores), detected)


def pick(profiles: list[Profile], total: int) -> list[tuple[Profile, str]]:
    """Hard cases first (HARD_PER_KIND each), then round-robin across families."""
    chosen: list[tuple[Profile, str]] = []
    used: set[Path] = set()
    for kind in ("intro_loud", "no_clear_drop", "double_drop"):
        for p in [p for p in profiles if kind in p.kinds and p.candidate.path not in used][:HARD_PER_KIND]:
            chosen.append((p, kind))
            used.add(p.candidate.path)
    by_family: dict[str, list[Profile]] = defaultdict(list)
    for p in profiles:
        if p.candidate.path not in used and not p.kinds:
            by_family[p.candidate.family].append(p)
    while len(chosen) < total and any(by_family.values()):
        for family in sorted(by_family):
            if by_family[family] and len(chosen) < total:
                chosen.append((by_family[family].pop(0), f"typical:{family}"))
    return chosen


def write_manifest(chosen: list[tuple[Profile, str]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "bpm", "genre", "family", "slice", "flags", "detected_s"])
        for p, slice_name in chosen:
            c = p.candidate
            writer.writerow([c.path, c.bpm, c.genre, c.family, slice_name, "|".join(p.kinds), p.detected_s])
    logger.info(f"Wrote manifest ({len(chosen)} tracks) to {out}")


def write_crate(paths: list[Path]) -> Path:
    """Write the crate into the synced Serato folder (never overwrites another crate)."""
    from serato_crate import SeratoCrate

    from music_minion.core.config import load_config
    from music_minion.domain.playlists.exporters import _serato_track_path

    config = load_config()
    crate_path = SERATO_ROOT / "_Serato_" / "Subcrates" / f"{CRATE_NAME}.crate"
    records = [("otrk", [("ptrk", _serato_track_path(str(p), config.syncthing))]) for p in paths]
    header = [("vrsn", "1.0/Serato ScratchLive Crate")]
    header += [("ovct", [("tvcn", col), ("tvcw", "0")]) for col in ("track", "artist", "bpm", "genre")]
    SeratoCrate(header + records).write(crate_path)
    return crate_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--total", type=int, default=50)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    pool = build_pool(load_uncued(args.seed))
    logger.info(f"Profiling {len(pool)} un-cued candidates")
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        profiles = [p for p in executor.map(profile, pool) if p is not None]
    chosen = pick(profiles, args.total)
    for p, slice_name in chosen:
        logger.info(f"{slice_name:<22} {p.candidate.bpm:>6.1f}  {p.candidate.path.name}")
    if not args.dry_run:
        write_manifest(chosen, args.manifest)
        logger.info(f"Wrote Serato crate to {write_crate([p.candidate.path for p, _ in chosen])}")


if __name__ == "__main__":
    main()
