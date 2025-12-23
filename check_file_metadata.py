#!/usr/bin/env python3
"""
Check the actual file metadata for track 5981
"""

from mutagen import File

file_path = "/home/kevin/Music/EDM/2025/Jul 25/DUBSTAR 101 (ALLEYCVT FLIP) - [Rihanna - Rockstar 101].mp3"

print(f"Checking metadata for: {file_path}")

try:
    audio = File(file_path)
    if audio:
        print("Raw metadata keys:", list(audio.keys()))
        for key in audio.keys():
            print(f"  {key}: {audio[key]}")
    else:
        print("Could not load audio file")
except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
