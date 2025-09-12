"""
Music library scanning and metadata extraction
"""

import os
import random
from pathlib import Path
from typing import List, Optional, Dict, Any, NamedTuple
from mutagen import File as MutagenFile
from mutagen.id3 import ID3NoHeaderError

from .config import Config


class Track(NamedTuple):
    """Represents a music track with metadata."""
    file_path: str
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[int] = None
    duration: Optional[float] = None  # in seconds
    bitrate: Optional[int] = None
    file_size: int = 0
    format: Optional[str] = None
    key: Optional[str] = None  # Musical key (e.g., "Am", "C#m")
    bpm: Optional[float] = None  # Beats per minute


def get_tag_value(audio_file: MutagenFile, tag_names: List[str]) -> Optional[str]:
    """Get tag value, trying multiple possible tag names."""
    for tag_name in tag_names:
        value = audio_file.get(tag_name)
        if value:
            # Handle different formats
            if isinstance(value, list) and value:
                return str(value[0])
            return str(value)
    return None


def extract_metadata_from_filename(file_path: str) -> Dict[str, Any]:
    """Extract basic info from filename as fallback."""
    path = Path(file_path)
    title = path.stem
    artist = None
    
    # Try to parse "Artist - Title" format
    if ' - ' in title:
        parts = title.split(' - ', 1)
        if len(parts) == 2:
            artist = parts[0].strip()
            title = parts[1].strip()
    
    # Get file size
    try:
        file_size = os.path.getsize(file_path)
    except OSError:
        file_size = 0
    
    return {
        'title': title,
        'artist': artist,
        'format': path.suffix.lower(),
        'file_size': file_size
    }


def extract_track_metadata(file_path: str) -> Track:
    """Extract metadata from audio file using mutagen."""
    try:
        audio_file = MutagenFile(file_path)
        if audio_file is None:
            # File couldn't be read by mutagen, use filename
            fallback = extract_metadata_from_filename(file_path)
            return Track(
                file_path=file_path,
                title=fallback['title'],
                artist=fallback['artist'],
                format=fallback['format'],
                file_size=fallback['file_size']
            )
        
        # Extract common metadata
        title = get_tag_value(audio_file, ['TIT2', '\xa9nam', 'TITLE'])
        artist = get_tag_value(audio_file, ['TPE1', '\xa9ART', 'ARTIST'])
        album = get_tag_value(audio_file, ['TALB', '\xa9alb', 'ALBUM'])
        genre = get_tag_value(audio_file, ['TCON', '\xa9gen', 'GENRE'])
        
        # Extract DJ metadata
        key = get_tag_value(audio_file, ['TKEY', 'KEY', 'INITIAL_KEY', '\xa9key'])
        bpm_str = get_tag_value(audio_file, ['TBPM', 'BPM', 'BEATS_PER_MINUTE', '\xa9bpm'])
        bpm = None
        if bpm_str:
            try:
                bpm = float(bpm_str)
            except (ValueError, TypeError):
                pass
        
        # Extract year
        year = None
        year_str = get_tag_value(audio_file, ['TDRC', '\xa9day', 'DATE', 'YEAR'])
        if year_str:
            try:
                # Handle various year formats
                year_str = str(year_str).split('-')[0]  # Take first part of date
                year = int(year_str)
            except (ValueError, TypeError):
                pass
        
        # Extract technical info
        duration = None
        bitrate = None
        if hasattr(audio_file, 'info'):
            duration = getattr(audio_file.info, 'length', None)
            bitrate = getattr(audio_file.info, 'bitrate', None)
        
        # Get file format and size
        format = Path(file_path).suffix.lower()
        file_size = os.path.getsize(file_path)
        
        # Fallback to filename if no title
        if not title:
            title = Path(file_path).stem
        
        return Track(
            file_path=file_path,
            title=title,
            artist=artist,
            album=album,
            genre=genre,
            year=year,
            duration=duration,
            bitrate=bitrate,
            file_size=file_size,
            format=format,
            key=key,
            bpm=bpm
        )
        
    except (ID3NoHeaderError, Exception) as e:
        print(f"Warning: Could not read metadata from {file_path}: {e}")
        fallback = extract_metadata_from_filename(file_path)
        return Track(
            file_path=file_path,
            title=fallback['title'],
            artist=fallback['artist'],
            format=fallback['format'],
            file_size=fallback['file_size']
        )


def is_supported_format(file_path: Path, supported_formats: List[str]) -> bool:
    """Check if file format is supported."""
    return file_path.suffix.lower() in supported_formats


def scan_directory(directory: Path, config: Config) -> List[Track]:
    """Scan a directory for music files and extract metadata."""
    tracks = []
    
    try:
        # Get all files if recursive, otherwise just immediate files
        if config.music.scan_recursive:
            files = directory.rglob('*')
        else:
            files = directory.iterdir()
        
        for file_path in files:
            if file_path.is_file() and is_supported_format(file_path, config.music.supported_formats):
                try:
                    track = extract_track_metadata(str(file_path))
                    tracks.append(track)
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    
    except PermissionError:
        print(f"Permission denied accessing: {directory}")
    except Exception as e:
        print(f"Error scanning directory {directory}: {e}")
    
    return tracks


def scan_music_library(config: Config, show_progress: bool = True) -> List[Track]:
    """Scan all configured library paths for music files."""
    all_tracks = []
    
    if show_progress:
        print("Scanning music library...")
    
    for library_path in config.music.library_paths:
        path = Path(library_path).expanduser()
        if not path.exists():
            print(f"Warning: Library path does not exist: {path}")
            continue
        
        if show_progress:
            print(f"Scanning: {path}")
        
        tracks = scan_directory(path, config)
        all_tracks.extend(tracks)
    
    if show_progress:
        print(f"Library scan complete: {len(all_tracks)} tracks found")
    
    return all_tracks


def get_random_track(tracks: List[Track]) -> Optional[Track]:
    """Get a random track from the library."""
    return random.choice(tracks) if tracks else None


def search_tracks(tracks: List[Track], query: str) -> List[Track]:
    """Search tracks by title, artist, album, or key."""
    query = query.lower()
    results = []
    
    for track in tracks:
        # Search in various fields
        search_fields = [
            track.title or '',
            track.artist or '',
            track.album or '',
            track.genre or '',
            track.key or '',
            Path(track.file_path).name
        ]
        
        if any(query in field.lower() for field in search_fields):
            results.append(track)
    
    return results


def get_tracks_by_key(tracks: List[Track], key: str) -> List[Track]:
    """Get all tracks in a specific key."""
    key = key.lower()
    return [track for track in tracks 
            if track.key and key in track.key.lower()]


def get_tracks_by_bpm_range(tracks: List[Track], min_bpm: float, max_bpm: float) -> List[Track]:
    """Get tracks within a BPM range."""
    return [track for track in tracks 
            if track.bpm and min_bpm <= track.bpm <= max_bpm]


def get_tracks_by_artist(tracks: List[Track], artist: str) -> List[Track]:
    """Get all tracks by a specific artist."""
    artist = artist.lower()
    return [track for track in tracks 
            if track.artist and artist in track.artist.lower()]


def get_tracks_by_album(tracks: List[Track], album: str) -> List[Track]:
    """Get all tracks from a specific album."""
    album = album.lower()
    return [track for track in tracks 
            if track.album and album in track.album.lower()]


def get_display_name(track: Track) -> str:
    """Get a display-friendly name for the track."""
    if track.artist and track.title:
        return f"{track.artist} - {track.title}"
    elif track.title:
        return track.title
    else:
        return Path(track.file_path).stem


def get_duration_str(track: Track) -> str:
    """Get duration as a formatted string (MM:SS)."""
    if not track.duration:
        return "??:??"
    
    minutes = int(track.duration // 60)
    seconds = int(track.duration % 60)
    return f"{minutes:02d}:{seconds:02d}"


def get_dj_info(track: Track) -> str:
    """Get DJ-relevant info (key, BPM, year) as a formatted string."""
    info_parts = []
    
    if track.year:
        info_parts.append(str(track.year))
    if track.key:
        info_parts.append(track.key)
    if track.bpm:
        info_parts.append(f"{track.bpm:.0f} BPM")
    if track.genre:
        info_parts.append(track.genre)
    
    return " • ".join(info_parts) if info_parts else "No DJ metadata"


def get_library_stats(tracks: List[Track]) -> Dict[str, Any]:
    """Get statistics about the music library."""
    if not tracks:
        return {
            'total_tracks': 0,
            'total_duration': 0,
            'total_size': 0,
            'artists': 0,
            'albums': 0,
            'formats': {},
            'keys': {},
            'avg_bpm': None,
            'tracks_with_bpm': 0,
            'tracks_with_key': 0
        }
    
    total_duration = sum(track.duration or 0 for track in tracks)
    total_size = sum(track.file_size for track in tracks)
    
    artists = set()
    albums = set()
    formats = {}
    keys = {}
    bpm_values = []
    
    tracks_with_bpm = 0
    tracks_with_key = 0
    
    for track in tracks:
        if track.artist:
            artists.add(track.artist)
        if track.album:
            albums.add(track.album)
        if track.format:
            formats[track.format] = formats.get(track.format, 0) + 1
        if track.key:
            keys[track.key] = keys.get(track.key, 0) + 1
            tracks_with_key += 1
        if track.bpm:
            bpm_values.append(track.bpm)
            tracks_with_bpm += 1
    
    avg_bpm = sum(bpm_values) / len(bpm_values) if bpm_values else None
    
    return {
        'total_tracks': len(tracks),
        'total_duration': total_duration,
        'total_duration_str': format_duration(total_duration),
        'total_size': total_size,
        'total_size_str': format_size(total_size),
        'artists': len(artists),
        'albums': len(albums),
        'formats': formats,
        'keys': keys,
        'avg_bpm': avg_bpm,
        'tracks_with_bpm': tracks_with_bpm,
        'tracks_with_key': tracks_with_key
    }


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable string."""
    if seconds == 0:
        return "0:00"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def format_size(bytes_size: int) -> str:
    """Format file size in bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"