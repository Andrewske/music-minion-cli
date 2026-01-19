#!/usr/bin/env python3
"""Convert audio files to Opus format.

Recursively finds audio files in source directory and converts them to Opus.
Supports MP3, WAV, FLAC, M4A, and AIFF formats.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


def convert_to_opus(
    src: Path,
    dest: Path,
    bitrate: str = "128k",
    flatten: bool = True,
    strip_prefix: str | None = None,
) -> tuple[int, int, int]:
    """Convert audio files to Opus format.

    Args:
        src: Source directory containing audio files
        dest: Destination directory for converted files
        bitrate: Opus bitrate (e.g., "128k", "96k", "192k")
        flatten: If True, flatten directory structure
        strip_prefix: Regex pattern to strip from filenames

    Returns:
        Tuple of (converted, skipped, failed) counts
    """
    dest.mkdir(parents=True, exist_ok=True)

    audio_extensions = {".mp3", ".wav", ".flac", ".m4a", ".aiff"}
    converted = 0
    skipped = 0
    failed = 0

    for audio_file in src.rglob("*"):
        if audio_file.suffix.lower() not in audio_extensions:
            continue

        filename = audio_file.name

        # Strip prefix if specified
        clean_name = filename
        if strip_prefix:
            clean_name = re.sub(strip_prefix, "", filename)

        base = clean_name.rsplit(".", 1)[0]

        if flatten:
            outfile = dest / f"{base}.opus"
        else:
            rel_path = audio_file.relative_to(src).parent
            out_dir = dest / rel_path
            out_dir.mkdir(parents=True, exist_ok=True)
            outfile = out_dir / f"{base}.opus"

        if outfile.exists():
            skipped += 1
            continue

        print(f"CONVERT: {filename}")
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(audio_file),
                    "-c:a",
                    "libopus",
                    "-b:a",
                    bitrate,
                    str(outfile),
                    "-loglevel",
                    "error",
                ],
                capture_output=True,
                timeout=120,
            )
            if result.returncode == 0:
                converted += 1
            else:
                print(f"  FAILED: {result.stderr.decode()[:200]}")
                failed += 1
        except subprocess.TimeoutExpired:
            print("  ERROR: Timeout")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

    return converted, skipped, failed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert audio files to Opus format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ~/Music/EDM/2025 ~/Music/radio-library
  %(prog)s ~/Music/EDM/2025 ~/Music/radio-library --bitrate 192k
  %(prog)s ~/Music/EDM/2025 ~/Music/radio-library --preserve-structure
  %(prog)s ~/Music/EDM/2025 ~/Music/radio-library --strip-prefix "^[A-Za-z]+ 25_"
        """,
    )
    parser.add_argument("source", type=Path, help="Source directory")
    parser.add_argument("destination", type=Path, help="Destination directory")
    parser.add_argument(
        "--bitrate",
        "-b",
        default="128k",
        help="Opus bitrate (default: 128k)",
    )
    parser.add_argument(
        "--preserve-structure",
        "-p",
        action="store_true",
        help="Preserve directory structure (default: flatten)",
    )
    parser.add_argument(
        "--strip-prefix",
        "-s",
        help="Regex pattern to strip from filenames",
    )

    args = parser.parse_args()

    if not args.source.exists():
        print(f"Error: Source directory does not exist: {args.source}")
        return 1

    print(f"Source: {args.source}")
    print(f"Destination: {args.destination}")
    print(f"Bitrate: {args.bitrate}")
    print(f"Flatten: {not args.preserve_structure}")
    if args.strip_prefix:
        print(f"Strip prefix: {args.strip_prefix}")
    print()

    converted, skipped, failed = convert_to_opus(
        src=args.source,
        dest=args.destination,
        bitrate=args.bitrate,
        flatten=not args.preserve_structure,
        strip_prefix=args.strip_prefix,
    )

    print()
    print("=== DONE ===")
    print(f"Converted: {converted}")
    print(f"Skipped (exists): {skipped}")
    print(f"Failed: {failed}")
    print(f"Total files: {len(list(args.destination.glob('*.opus')))}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
