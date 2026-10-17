#!/usr/bin/env python3
"""Prototype: detect the first drop in local tracks and score it against Serato cues.

Detector: bass-band energy per beat, find the beat where the next 4 bars are loud
and the previous 2 bars are quiet (bass pulled out during the buildup).

Ground truth: Serato hot cues read from file tags. By default any cue counts
(lenient: "did we land on *a* cue"). Stricter ground truth:
  --drop-slot N     only hot cue slot N (1-8, as numbered in Serato) counts
  --drop-cues-only  only cues whose name contains "drop" count

Half-time BPM tags (< 90, e.g. 75 for 150 dubstep) are doubled for analysis so
"bars" mean the same thing across genres.

Usage:
    uv run python scripts/drop_detection_eval.py --limit 50
    uv run python scripts/drop_detection_eval.py --drop-slot 8 --out /tmp/drops.csv
"""

import argparse
import base64
import csv
import random
import sqlite3
import struct
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import NamedTuple

import numpy as np
from loguru import logger
from mutagen import File as MutagenFile

DB_PATH = Path.home() / ".local/share/music-minion/music_minion.db"
SAMPLE_RATE = 11025
FFT_SIZE = 2048
HOP = 256
BASS_HZ = (30.0, 150.0)
POST_BEATS = 16  # 4 bars after the candidate must be loud
PRE_BEATS = 8  # 2 bars before the candidate should be quiet
MIN_START_BEATS = 32  # ignore the first 8 bars (intros often open loud)
FIRST_DROP_RATIO = 0.6  # first candidate scoring >= 60% of the best one wins


class Cue(NamedTuple):
    seconds: float
    name: str
    slot: int  # 1-based, matches Serato's hot cue buttons


class Result(NamedTuple):
    path: str
    bpm: float
    detected_s: float | None
    best_s: float | None
    confidence: float
    cues: list[Cue]
    duration_s: float


# --- Serato Markers2 parsing -------------------------------------------------


def _b64(data: bytes) -> bytes:
    """Decode Serato's sloppy base64 (newlines, missing/extra padding)."""
    clean = data.replace(b"\n", b"").rstrip(b"\x00")
    if len(clean) % 4 == 1:
        clean = clean[:-1]
    return base64.b64decode(clean + b"=" * (-len(clean) % 4))


def _raw_markers2(path: Path) -> bytes | None:
    """Return the Markers2 tag bytes for MP3 (GEOB), MP4, or Vorbis containers."""
    tags = MutagenFile(path).tags
    if tags is None:
        return None
    for key in tags.keys():
        lowered = str(key).lower()
        if "markers2" in lowered or "markers_v2" in lowered or "markersv2" in lowered:
            value = tags[key]
            raw = getattr(value, "data", None) or (value[0] if isinstance(value, list) else value)
            return raw if isinstance(raw, bytes) else bytes(raw) if not isinstance(raw, str) else raw.encode()
    return None


def _unwrap_markers2(raw: bytes) -> bytes:
    """Strip container wrappers down to the decoded entry payload."""
    if not raw.startswith(b"\x01\x01"):
        inner = _b64(raw)
        marker = b"Serato Markers2\x00"
        raw = inner[inner.find(marker) + len(marker) :]
    return _b64(raw[2:])


def _parse_cue(data: bytes) -> Cue:
    position_ms = struct.unpack(">I", data[2:6])[0]
    name = data[12:].split(b"\x00", 1)[0].decode("utf-8", errors="replace")
    return Cue(position_ms / 1000.0, name, data[1] + 1)


def read_serato_cues(path: Path) -> list[Cue]:
    """Read hot cues from a file's Serato Markers2 tag ([] if none/unparseable)."""
    try:
        raw = _raw_markers2(path)
        payload = _unwrap_markers2(raw)[2:] if raw else b""
    except (ValueError, OSError, struct.error) as e:
        logger.debug(f"Markers2 parse failed for {path}: {e}")
        return []
    cues, offset = [], 0
    while offset < len(payload) and payload[offset] != 0:
        name_end = payload.index(b"\x00", offset)
        name = payload[offset:name_end]
        length = struct.unpack(">I", payload[name_end + 1 : name_end + 5])[0]
        data = payload[name_end + 5 : name_end + 5 + length]
        if name == b"CUE":
            cues.append(_parse_cue(data))
        offset = name_end + 5 + length
    return sorted(cues)


# --- Audio + detection -------------------------------------------------------


def analysis_bpm(bpm: float) -> float:
    """Undo half-time tagging: 75 BPM dubstep is analysed as 150."""
    return bpm * 2 if bpm < 90 else bpm


def load_audio(path: Path) -> np.ndarray:
    """Decode to mono float32 at SAMPLE_RATE via ffmpeg."""
    cmd = ["ffmpeg", "-v", "quiet", "-i", str(path), "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-"]
    result = subprocess.run(cmd, capture_output=True, check=True)
    return np.frombuffer(result.stdout, dtype=np.float32)


def bass_envelope(samples: np.ndarray) -> np.ndarray:
    """Bass-band power per STFT frame (hop = HOP samples)."""
    n_frames = 1 + (len(samples) - FFT_SIZE) // HOP
    idx = np.arange(FFT_SIZE)[None, :] + HOP * np.arange(n_frames)[:, None]
    spectrum = np.abs(np.fft.rfft(samples[idx] * np.hanning(FFT_SIZE), axis=1)) ** 2
    freqs = np.fft.rfftfreq(FFT_SIZE, 1 / SAMPLE_RATE)
    band = (freqs >= BASS_HZ[0]) & (freqs <= BASS_HZ[1])
    return spectrum[:, band].sum(axis=1)


def beat_phase(env: np.ndarray, frames_per_beat: float) -> float:
    """Frame offset of the beat grid that best lines up with kick onsets."""
    onsets = np.maximum(0, np.diff(env, prepend=env[0]))
    phases = np.arange(0, frames_per_beat, 1.0)
    grid = np.arange(0, len(onsets) - frames_per_beat, frames_per_beat)
    scores = [onsets[(grid + p).astype(int)].sum() for p in phases]
    return float(phases[int(np.argmax(scores))])


def per_beat_energy(env: np.ndarray, frames_per_beat: float, phase: float) -> np.ndarray:
    starts = np.arange(phase, len(env) - frames_per_beat, frames_per_beat).astype(int)
    width = max(1, int(frames_per_beat))
    return np.array([env[s : s + width].mean() for s in starts])


def drop_scores(beats: np.ndarray) -> np.ndarray:
    """Score each beat as a drop start: loud-after x quiet-before contrast."""
    loud = np.percentile(beats, 90) + 1e-9
    scores = np.zeros(len(beats))
    for i in range(max(MIN_START_BEATS, PRE_BEATS), len(beats) - POST_BEATS):
        post = beats[i : i + POST_BEATS].mean()
        pre = beats[i - PRE_BEATS : i].mean()
        scores[i] = min(post / loud, 1.0) * np.log1p(post / (pre + 1e-9 * loud))
    return scores


def local_peaks(scores: np.ndarray, radius: int = PRE_BEATS) -> np.ndarray:
    """Beats that are the max of their +/- radius neighbourhood (kills the ramp-up
    beats just before a drop, which also score high)."""
    padded = np.pad(scores, radius, constant_values=-np.inf)
    windows = np.lib.stride_tricks.sliding_window_view(padded, 2 * radius + 1)
    return np.flatnonzero((scores > 0) & (scores >= windows.max(axis=1)))


def pick_drops(scores: np.ndarray) -> tuple[int | None, int | None, float]:
    """Return (first-drop beat, best beat, confidence = best score)."""
    best = int(np.argmax(scores))
    if scores[best] <= 0:
        return None, None, 0.0
    peaks = local_peaks(scores)
    first = int(peaks[scores[peaks] >= FIRST_DROP_RATIO * scores[best]][0])
    return first, best, float(scores[best])


def detect_drop(path: Path, bpm: float) -> tuple[float | None, float | None, float, float]:
    """Return (first_drop_s, best_drop_s, confidence, duration_s)."""
    samples = load_audio(path)
    env = bass_envelope(samples)
    frames_per_beat = (60.0 / analysis_bpm(bpm)) * SAMPLE_RATE / HOP
    phase = beat_phase(env, frames_per_beat)
    first, best, conf = pick_drops(drop_scores(per_beat_energy(env, frames_per_beat, phase)))
    to_s = lambda beat: None if beat is None else (phase + beat * frames_per_beat) * HOP / SAMPLE_RATE  # noqa: E731
    return to_s(first), to_s(best), conf, len(samples) / SAMPLE_RATE


# --- Eval harness ------------------------------------------------------------


class Selection(NamedTuple):
    limit: int
    drop_only: bool
    drop_slot: int | None
    seed: int
    manifest: Path | None


def load_manifest(manifest: Path) -> dict[str, str]:
    """path -> slice name, from scripts/build_drop_label_set.py output."""
    with manifest.open() as f:
        return {row["path"]: row["slice"] for row in csv.DictReader(f)}


def load_candidates(manifest: Path | None) -> list[tuple[Path, float]]:
    """Local tracks with a BPM, from the DB (restricted to the manifest if given)."""
    allowed = load_manifest(manifest) if manifest else None
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT local_path, bpm FROM tracks WHERE local_path IS NOT NULL AND bpm > 0"
        ).fetchall()
    return [(Path(p), float(b)) for p, b in rows if Path(p).exists() and (allowed is None or p in allowed)]


def truth_cues(cues: list[Cue], drop_only: bool, drop_slot: int | None) -> list[Cue]:
    if drop_slot is not None:
        return [c for c in cues if c.slot == drop_slot]
    return [c for c in cues if "drop" in c.name.lower()] if drop_only else cues


def evaluate_one(path: Path, bpm: float, cues: list[Cue]) -> Result | None:
    try:
        first, best, conf, duration = detect_drop(path, bpm)
    except (subprocess.CalledProcessError, ValueError) as e:
        logger.warning(f"Detection failed for {path}: {e}")
        return None
    return Result(str(path), bpm, first, best, conf, cues, duration)


def select_tracks(sel: Selection) -> list[tuple[Path, float, list[Cue]]]:
    candidates = load_candidates(sel.manifest)
    random.Random(sel.seed).shuffle(candidates)
    picked = []
    for path, bpm in candidates:
        cues = truth_cues(read_serato_cues(path), sel.drop_only, sel.drop_slot)
        if cues:
            picked.append((path, bpm, cues))
        if len(picked) >= sel.limit:
            break
    return picked


def run(sel: Selection, workers: int) -> list[Result]:
    tracks = select_tracks(sel)
    logger.info(f"Evaluating {len(tracks)} labeled tracks ({sel})")
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(evaluate_one, *t) for t in tracks]
        return [r for f in as_completed(futures) if (r := f.result()) is not None]


def bars_off(result: Result, seconds: float | None) -> float | None:
    if seconds is None:
        return None
    nearest = min(abs(c.seconds - seconds) for c in result.cues)
    return nearest / (4 * 60.0 / analysis_bpm(result.bpm))


def random_baseline(results: list[Result], tolerance_bars: float, seed: int) -> float:
    """Hit rate of a uniformly random guess: calibrates how lenient 'nearest cue' is."""
    rng = random.Random(seed)
    hits = sum(
        (bars_off(r, rng.uniform(0, r.duration_s)) or 99) <= tolerance_bars
        for r in results
        for _ in range(20)
    )
    return hits / (20 * len(results))


def hit_rate(results: list[Result], field: str, tolerance_bars: float) -> float:
    offs = [bars_off(r, getattr(r, field)) for r in results]
    return sum(o is not None and o <= tolerance_bars for o in offs) / len(results)


def report(results: list[Result], seed: int) -> None:
    if not results:
        logger.warning("No results to report")
        return
    avg_cues = np.mean([len(r.cues) for r in results])
    logger.info(f"{len(results)} tracks, {avg_cues:.1f} cues/track on average")
    for tol in (0.5, 1, 2, 4):
        logger.info(
            f"within {tol:>3} bars | first-drop {hit_rate(results, 'detected_s', tol):5.0%}"
            f" | best-drop {hit_rate(results, 'best_s', tol):5.0%}"
            f" | random guess {random_baseline(results, tol, seed):5.0%}"
        )


def report_slices(results: list[Result], slices: dict[str, str]) -> None:
    """Per-slice hit rate at 2 bars (manifest runs only)."""
    grouped: dict[str, list[Result]] = {}
    for r in results:
        grouped.setdefault(slices.get(r.path, "?"), []).append(r)
    for name, group in sorted(grouped.items()):
        logger.info(f"  {name:<22} n={len(group):>2} | within 2 bars {hit_rate(group, 'detected_s', 2):5.0%}")


def write_csv(results: list[Result], out: Path) -> None:
    with out.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "bpm", "detected_s", "best_s", "confidence", "bars_off", "cues"])
        for r in sorted(results, key=lambda r: -(bars_off(r, r.detected_s) or 99)):
            off = bars_off(r, r.detected_s)
            cues = "; ".join(f"{c.seconds:.1f}:{c.name}" for c in r.cues)
            writer.writerow([r.path, r.bpm, r.detected_s, r.best_s, f"{r.confidence:.2f}", off, cues])
    logger.info(f"Wrote per-track results to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--manifest", type=Path, help="Only evaluate tracks listed in this manifest CSV")
    parser.add_argument("--drop-slot", type=int, choices=range(1, 9), help="Only this hot cue slot counts")
    parser.add_argument("--drop-cues-only", action="store_true", help="Only cues named '*drop*' count")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out", type=Path, default=Path("/tmp/drop_detection_eval.csv"))
    args = parser.parse_args()
    limit = 10_000 if args.manifest else args.limit
    sel = Selection(limit, args.drop_cues_only, args.drop_slot, args.seed, args.manifest)
    results = run(sel, args.workers)
    report(results, args.seed)
    if args.manifest and results:
        report_slices(results, load_manifest(args.manifest))
    write_csv(results, args.out)


if __name__ == "__main__":
    main()
