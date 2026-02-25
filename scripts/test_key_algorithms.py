#!/usr/bin/env python3
"""Test different key detection algorithms on low confidence tracks."""

import essentia.standard as es
from pathlib import Path

# Parse low confidence file
low_conf_tracks = []
with open("low_confidence_keys.txt") as f:
    for line in f:
        if line.startswith("#"):
            continue
        parts = line.strip().split("\t")
        if len(parts) >= 3:
            path = Path(parts[0])
            detected = parts[1].split("=")[1]
            conf = float(parts[2].split("=")[1])
            low_conf_tracks.append({"path": path, "original_key": detected, "original_conf": conf})

print(f"Testing {len(low_conf_tracks)} low confidence tracks...\n")

profiles = ["temperley", "edma", "edmm"]
results = []
better_with_edm = 0

for i, track in enumerate(low_conf_tracks[:10]):
    path = track["path"]
    if not path.exists():
        continue

    try:
        audio = es.MonoLoader(filename=str(path), sampleRate=44100)()

        row = {
            "file": path.name[:35],
            "original": track['original_key'],
            "original_conf": track['original_conf']
        }

        best_conf = track['original_conf']
        best_profile = "KeyExtractor"

        for profile in profiles:
            key_algo = es.Key(profileType=profile)
            key, scale, strength, *_ = key_algo(audio)
            key_str = f"{key}{'m' if scale == 'minor' else ''}"
            row[profile] = key_str
            row[f"{profile}_conf"] = strength

            if strength > best_conf:
                best_conf = strength
                best_profile = profile

        row["best"] = best_profile
        row["best_conf"] = best_conf

        if best_profile != "KeyExtractor":
            better_with_edm += 1

        results.append(row)
        print(f"[{i+1}/10] {path.name[:50]}")

    except Exception as e:
        print(f"ERROR: {path.name}: {e}")

print("\n" + "=" * 95)
print(f"{'File':<37} {'Orig':<6} {'Conf':<5} {'edma':<6} {'Conf':<5} {'edmm':<6} {'Conf':<5} {'Best':<12}")
print("=" * 95)

for r in results:
    print(f"{r['file']:<37} {r['original']:<6} {r['original_conf']:.2f}  "
          f"{r.get('edma', '-'):<6} {r.get('edma_conf', 0):.2f}  "
          f"{r.get('edmm', '-'):<6} {r.get('edmm_conf', 0):.2f}  "
          f"{r['best']:<12}")

print("=" * 95)
print(f"\n{better_with_edm}/{len(results)} tracks have higher confidence with EDM profiles")
