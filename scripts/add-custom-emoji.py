#!/usr/bin/env python3
"""
Add custom emoji to Music Minion.

Usage:
    uv run scripts/add-custom-emoji.py --image path/to/emoji.png --name "my emoji"
    uv run scripts/add-custom-emoji.py --image ~/Downloads/cool.gif --name "cool"
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.backend.services.emoji_processor import process_emoji_image, delete_emoji_file
from music_minion.core.database import get_db_connection


def main() -> None:
    parser = argparse.ArgumentParser(description='Add custom emoji to Music Minion')
    parser.add_argument('--image', required=True, help='Path to image file (PNG, JPEG, GIF)')
    parser.add_argument('--name', required=True, help='Name for the emoji')
    args = parser.parse_args()

    # Read image file
    image_path = Path(args.image).expanduser()
    if not image_path.exists():
        print(f"Error: Image file not found: {image_path}")
        sys.exit(1)

    try:
        with open(image_path, 'rb') as f:
            file_content = f.read()
    except Exception as e:
        print(f"Error reading image: {e}")
        sys.exit(1)

    # Process image
    try:
        emoji_id, filename = process_emoji_image(file_content, image_path.name)
    except ValueError as e:
        print(f"Error processing image: {e}")
        sys.exit(1)

    # Insert into database
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO emoji_metadata (emoji_id, type, file_path, default_name, use_count)
                VALUES (?, 'custom', ?, ?, 0)
                """,
                (emoji_id, filename, args.name.strip())
            )
            conn.commit()
    except Exception as e:
        print(f"Error inserting into database: {e}")
        # Clean up file if database insert failed
        delete_emoji_file(filename)
        sys.exit(1)

    print("✅ Custom emoji added successfully!")
    print(f"   ID: {emoji_id}")
    print(f"   Name: {args.name}")
    print(f"   File: {filename}")


if __name__ == '__main__':
    main()
