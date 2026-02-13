"""Image processing for custom emojis. Shared by CLI script and backend."""

import io
import uuid
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageSequence

from music_minion.core.config import get_data_dir


MAX_SIZE = 128  # Max width/height in pixels
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB (prevents blocking)
MAX_FRAMES = 20  # Max GIF frames (prevents blocking)
ALLOWED_FORMATS = {'PNG', 'JPEG', 'GIF'}


def get_custom_emojis_dir() -> Path:
    """Get the custom emojis directory, creating if needed."""
    custom_dir = get_data_dir() / "custom_emojis"
    custom_dir.mkdir(exist_ok=True)
    return custom_dir


def process_emoji_image(file_content: bytes, original_filename: str) -> Tuple[str, str]:
    """
    Process uploaded emoji image: validate, resize, save.

    Args:
        file_content: Raw bytes of the image file
        original_filename: Original filename (used only for error messages)

    Returns:
        Tuple of (emoji_id, filename)
        emoji_id: UUID string (type column distinguishes custom from unicode)
        filename: filename of saved file

    Raises:
        ValueError: If file too large, wrong format, or too many frames
    """
    # Validate file size
    if len(file_content) > MAX_FILE_SIZE:
        raise ValueError(f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB")

    # Open image
    img = Image.open(io.BytesIO(file_content))

    # Validate format
    if img.format not in ALLOWED_FORMATS:
        raise ValueError(f"Unsupported format: {img.format}. Allowed: {ALLOWED_FORMATS}")

    # Generate unique filename
    file_ext = img.format.lower()
    emoji_id = str(uuid.uuid4())  # Just UUID, no "custom:" prefix
    filename = f"{emoji_id}.{file_ext}"

    # Resize image
    output_path = get_custom_emojis_dir() / filename

    if img.format == 'GIF' and getattr(img, 'is_animated', False):
        # Check frame count
        frame_count = getattr(img, 'n_frames', 1)
        if frame_count > MAX_FRAMES:
            raise ValueError(f"Too many frames ({frame_count}). Max: {MAX_FRAMES}")

        # Preserve GIF animation
        frames = []
        durations = []

        for frame in ImageSequence.Iterator(img):
            # Resize frame preserving aspect ratio
            frame = frame.copy()
            frame.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)
            frames.append(frame)
            durations.append(frame.info.get('duration', 100))

        # Save animated GIF
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            optimize=True
        )
    else:
        # Resize static image
        img.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)
        img.save(output_path, optimize=True)

    return emoji_id, filename


def delete_emoji_file(file_path: str) -> None:
    """Delete a custom emoji file.

    Args:
        file_path: Filename (not full path) of the emoji file to delete
    """
    full_path = get_custom_emojis_dir() / file_path
    if full_path.exists():
        full_path.unlink()
