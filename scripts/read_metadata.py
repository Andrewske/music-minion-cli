#!/usr/bin/env python3
"""
Script to read and display all metadata from an audio file
"""

import sys
from pathlib import Path

from mutagen import File as MutagenFile


def read_metadata(local_path):
    """Read all metadata from an audio file."""
    path = Path(local_path)

    if not path.exists():
        print(f"Error: File not found: {local_path}")
        return

    print(f"Reading metadata from: {local_path}")
    print("=" * 80)

    try:
        # Try to load with mutagen
        audio = MutagenFile(local_path)

        if audio is None:
            print("Error: Could not read file with mutagen")
            return

        # Display file info
        print("\n[FILE INFO]")
        print(f"Format: {audio.mime[0] if audio.mime else 'Unknown'}")

        if hasattr(audio.info, "length"):
            print(
                f"Duration: {audio.info.length:.2f} seconds ({int(audio.info.length // 60)}:{int(audio.info.length % 60):02d})"
            )
        if hasattr(audio.info, "bitrate"):
            print(f"Bitrate: {audio.info.bitrate} bps")
        if hasattr(audio.info, "sample_rate"):
            print(f"Sample Rate: {audio.info.sample_rate} Hz")
        if hasattr(audio.info, "channels"):
            print(f"Channels: {audio.info.channels}")

        # Display all tags
        print("\n[METADATA TAGS]")
        if audio.tags:
            # Common tag mappings
            common_tags = {
                "TIT2": "Title",
                "TPE1": "Artist",
                "TPE2": "Album Artist",
                "TALB": "Album",
                "TDRC": "Year/Date",
                "TCON": "Genre",
                "TBPM": "BPM",
                "TKEY": "Key",
                "COMM": "Comment",
                "APIC": "Picture/Artwork",
            }

            # First show common tags in readable format
            print("\nCommon Tags:")
            for tag_id, name in common_tags.items():
                if tag_id in audio.tags:
                    value = audio.tags[tag_id]
                    if tag_id == "APIC":
                        print(f"  {name}: [Image data present]")
                    else:
                        print(f"  {name}: {value}")

            # Then show all tags in raw format
            print("\nAll Tags (Raw):")
            for key, value in sorted(audio.tags.items()):
                if key.startswith("APIC"):
                    print(f"  {key}: [Binary image data, {len(str(value))} bytes]")
                else:
                    # Truncate very long values
                    val_str = str(value)
                    if len(val_str) > 100:
                        val_str = val_str[:97] + "..."
                    print(f"  {key}: {val_str}")
        else:
            print("  No metadata tags found")

        # Check for DJ-specific metadata
        print("\n[DJ-SPECIFIC METADATA]")
        dj_tags = [
            "TBPM",
            "TKEY",
            "COMM",
            "TXXX:INITIALKEY",
            "TXXX:ENERGY",
            "TXXX:COMMENT",
            "TXXX:RATING",
        ]
        found_dj = False
        for tag in dj_tags:
            if audio.tags and tag in audio.tags:
                print(f"  {tag}: {audio.tags[tag]}")
                found_dj = True
        if not found_dj:
            print("  No DJ-specific metadata found")

    except Exception as e:
        print(f"Error reading file: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Default to the file you asked about
        local_path = "/home/kevin/Music/EDM/2025/May 25/May 25_Dirtyhappy X Morgatron - BOOYAKA.m4a"
    else:
        local_path = sys.argv[1]

    read_metadata(local_path)
