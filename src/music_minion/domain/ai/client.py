"""
AI integration for Music Minion CLI using OpenAI Responses API
"""

import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from music_minion.core.config import get_config_dir
from music_minion.core.database import (
    get_track_by_path, get_track_notes, get_track_tags,
    add_tags, log_ai_request
)
from music_minion.domain.library import Track


class AIError(Exception):
    """Custom exception for AI-related errors."""
    pass


def get_api_key() -> Optional[str]:
    """Get OpenAI API key from environment variable or .env file."""
    # Check environment variable first
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        return api_key
    
    # Try to load from .env file in project root or config directory
    try:
        from dotenv import load_dotenv
        
        # Check project root .env file first
        project_root = Path.cwd()
        env_file = project_root / '.env'
        if env_file.exists():
            load_dotenv(env_file)
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                return api_key
        
        # Check config directory .env file
        config_env_file = get_config_dir() / '.env'
        if config_env_file.exists():
            load_dotenv(config_env_file)
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                return api_key
    except ImportError:
        pass
    
    # Fallback to legacy credentials file for backward compatibility
    credentials_file = get_config_dir() / 'credentials.toml'
    if credentials_file.exists():
        try:
            import tomllib
            with open(credentials_file, 'rb') as f:
                credentials = tomllib.load(f)
                return credentials.get('openai', {}).get('api_key')
        except Exception:
            pass
    
    return None


def store_api_key(api_key: str) -> None:
    """Store API key in .env file with restricted permissions."""
    # Store in config directory .env file
    env_file = get_config_dir() / '.env'
    
    # Ensure config directory exists
    env_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Read existing .env content to preserve other variables
    env_content = []
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                env_content = f.readlines()
        except Exception:
            pass
    
    # Update or add OPENAI_API_KEY
    updated = False
    for i, line in enumerate(env_content):
        if line.strip().startswith('OPENAI_API_KEY='):
            env_content[i] = f'OPENAI_API_KEY="{api_key}"\n'
            updated = True
            break
    
    if not updated:
        env_content.append(f'OPENAI_API_KEY="{api_key}"\n')
    
    # Write updated content
    with open(env_file, 'w') as f:
        f.writelines(env_content)
    
    # Set restrictive permissions (readable only by owner)
    env_file.chmod(0o600)


def get_user_prompt() -> str:
    """Get user's custom AI prompt from the markdown file."""
    prompt_file = get_config_dir() / 'ai-prompt.md'
    
    if prompt_file.exists():
        try:
            return prompt_file.read_text().strip()
        except Exception:
            pass
    
    # Return default prompt if file doesn't exist
    default_prompt = """# AI Music Analysis Instructions

Analyze each track individually based on its specific characteristics.

## Focus Areas
- Genre/subgenre specifics (not just "electronic" but "deep-house", "synthwave", etc.)
- Energy and tempo feel (based on actual BPM if available)
- Musical key mood implications (minor keys often darker, major brighter)
- Distinctive elements mentioned in user notes
- Production style and instrumentation

## Output
Return ONLY a comma-separated list of 3-6 specific tags.
Use lowercase, be precise, avoid generic terms.

Example good tags: deep-house, melancholic, driving-bass, minor-key, synth-heavy
Example bad tags: good, nice, music, song, electronic, rock
"""
    
    # Create default prompt file
    try:
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(default_prompt)
    except Exception:
        pass
    
    return default_prompt


def build_analysis_input(track: Track, notes: List[Dict[str, Any]], 
                        existing_tags: List[Dict[str, Any]]) -> str:
    """Build the input for AI analysis using Responses API format."""
    user_prompt = get_user_prompt()
    
    # Format track metadata
    metadata_lines = [
        f"**Title**: {track.title or 'Unknown'}",
        f"**Artist**: {track.artist or 'Unknown'}",
        f"**Album**: {track.album or 'Unknown'}",
        f"**Genre**: {track.genre or 'Unknown'}",
        f"**Year**: {track.year or 'Unknown'}",
    ]
    
    if track.key:
        metadata_lines.append(f"**Key**: {track.key}")
    if track.bpm:
        metadata_lines.append(f"**BPM**: {track.bpm}")
    
    metadata_section = "\n".join(metadata_lines)
    
    # Format user notes
    notes_section = ""
    if notes:
        note_texts = [note['note_text'] for note in notes]
        notes_section = f"\n\n## User Notes\n" + "\n".join(f"- {note}" for note in note_texts)
    
    # Format existing tags
    existing_section = ""
    if existing_tags:
        user_tags = [tag['tag_name'] for tag in existing_tags if tag['source'] == 'user']
        ai_tags = [tag['tag_name'] for tag in existing_tags if tag['source'] == 'ai']
        
        if user_tags:
            existing_section += f"\n\n## Existing User Tags\n{', '.join(user_tags)}"
        if ai_tags:
            existing_section += f"\n\n## Existing AI Tags\n{', '.join(ai_tags)}"
    
    input_text = f"""Analyze this track for music discovery tags:

{metadata_section}{notes_section}{existing_section}

Based on this specific track data, what makes it distinctive? Consider:
- The genre and subgenre characteristics
- The BPM and energy level (if provided)
- The musical key and its mood implications
- Any user notes about the track's character
- Avoid tags that are already present

Suggest 3-6 specific, discoverable tags that capture this track's unique qualities."""
    
    return input_text


def analyze_track_with_ai(track: Track, request_type: str = 'auto_analysis') -> Tuple[List[str], Dict[str, Any]]:
    """
    Analyze a track with AI using the Responses API and return tags and request metadata.
    
    Returns:
        Tuple of (tags_list, request_metadata)
    """
    api_key = get_api_key()
    if not api_key:
        raise AIError("No OpenAI API key found. Use 'ai setup <key>' to configure.")
    
    try:
        import openai
    except ImportError:
        raise AIError("OpenAI library not installed. Install with: pip install openai")
    
    # Get track from database to get ID
    db_track = get_track_by_path(track.file_path)
    if not db_track:
        raise AIError("Track not found in database")
    
    track_id = db_track['id']
    
    # Get existing notes and tags
    notes = get_track_notes(track_id)
    existing_tags = get_track_tags(track_id, include_blacklisted=True)
    
    # Build input for Responses API
    input_text = build_analysis_input(track, notes, existing_tags)
    
    # Prepare OpenAI client
    client = openai.OpenAI(api_key=api_key)
    
    start_time = time.time()
    
    try:
        # Make API request using Responses API - simple text output
        response = client.responses.create(
            model="gpt-4o-mini",
            instructions="Analyze this specific track and suggest 3-6 relevant tags based on the actual metadata, genre, BPM, key, and user notes provided. Focus on what makes THIS track distinctive. Return ONLY a comma-separated list of tags, nothing else. Be specific to the actual track data, not generic.",
            input=input_text
        )
        
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        
        # Parse response from Responses API - simple comma-separated tags
        output_text = response.output_text.strip()
        
        # Split by comma and clean up tags
        if output_text:
            tags = [tag.strip().lower() for tag in output_text.split(',') if tag.strip()]
        else:
            tags = []
        
        # Log successful request
        request_metadata = {
            'prompt_tokens': response.usage.input_tokens,
            'completion_tokens': response.usage.output_tokens,
            'response_time_ms': response_time_ms,
            'success': True
        }
        
        log_ai_request(
            track_id=track_id,
            request_type=request_type,
            model_name="gpt-4o-mini",
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            response_time_ms=response_time_ms,
            success=True
        )
        
        return tags, request_metadata
        
    except openai.APIError as e:
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        
        error_msg = f"OpenAI API error: {str(e)}"
        
        # Log failed request
        log_ai_request(
            track_id=track_id,
            request_type=request_type,
            model_name="gpt-4o-mini",
            prompt_tokens=0,
            completion_tokens=0,
            response_time_ms=response_time_ms,
            success=False,
            error_message=error_msg
        )
        
        raise AIError(error_msg)
    
    except Exception as e:
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        
        error_msg = f"Unexpected error: {str(e)}"
        
        log_ai_request(
            track_id=track_id,
            request_type=request_type,
            model_name="gpt-4o-mini",
            prompt_tokens=0,
            completion_tokens=0,
            response_time_ms=response_time_ms,
            success=False,
            error_message=error_msg
        )
        
        raise AIError(error_msg)


def analyze_and_tag_track(track: Track, request_type: str = 'auto_analysis') -> Dict[str, Any]:
    """
    Analyze a track and automatically add AI tags to the database.
    
    Returns:
        Dictionary with analysis results and metadata
    """
    try:
        tags, request_metadata = analyze_track_with_ai(track, request_type)
        
        if tags:
            # Get track ID
            db_track = get_track_by_path(track.file_path)
            track_id = db_track['id']
            
            # Add tags to database
            add_tags(track_id, tags, source='ai')
            
            return {
                'success': True,
                'tags_added': tags,
                'token_usage': {
                    'prompt_tokens': request_metadata['prompt_tokens'],
                    'completion_tokens': request_metadata['completion_tokens'],
                    'response_time_ms': request_metadata['response_time_ms']
                }
            }
        else:
            return {
                'success': True,
                'tags_added': [],
                'token_usage': {
                    'prompt_tokens': request_metadata['prompt_tokens'],
                    'completion_tokens': request_metadata['completion_tokens'],
                    'response_time_ms': request_metadata['response_time_ms']
                }
            }
    
    except AIError as e:
        return {
            'success': False,
            'error': str(e),
            'tags_added': []
        }


def format_usage_stats(stats: Dict[str, Any], period_name: str = "Total") -> str:
    """Format AI usage statistics for display."""
    if stats['total_requests'] == 0:
        return f"📊 {period_name} AI Usage: No requests yet"
    
    lines = [
        f"📊 {period_name} AI Usage",
        f"   Requests: {stats['total_requests']} ({stats['successful_requests']} successful)",
        f"   Tokens: {stats['total_tokens']:,} ({stats['total_prompt_tokens']:,} prompt + {stats['total_completion_tokens']:,} completion)",
        f"   Cost: ${stats['total_cost']:.4f}",
    ]
    
    if stats['avg_response_time']:
        lines.append(f"   Avg Response: {stats['avg_response_time']:.0f}ms")
    
    if stats['request_types']:
        lines.append("   Breakdown:")
        for req_type, data in stats['request_types'].items():
            lines.append(f"     {req_type}: {data['count']} requests (${data['cost']:.4f})")
    
    return "\n".join(lines)


def test_ai_prompt_with_random_track() -> Dict[str, Any]:
    """
    Test the AI prompt with a random track and return detailed results.
    
    Returns:
        Dictionary with test results, input, output, and metadata
    """
    from ...core.database import get_all_tracks, get_track_notes, get_track_tags, db_track_to_library_track
    import random
    from datetime import datetime
    
    # Get all tracks from database
    db_tracks = get_all_tracks()
    if not db_tracks:
        return {
            'success': False,
            'error': 'No tracks found in database. Run "scan" command first.'
        }
    
    # Pick a random track
    random_db_track = random.choice(db_tracks)
    track = db_track_to_library_track(random_db_track)
    track_id = random_db_track['id']
    
    # Get existing notes and tags
    notes = get_track_notes(track_id)
    existing_tags = get_track_tags(track_id, include_blacklisted=True)
    
    # Build the analysis input
    input_text = build_analysis_input(track, notes, existing_tags)
    
    # Get user prompt
    user_prompt = get_user_prompt()
    
    api_key = get_api_key()
    if not api_key:
        return {
            'success': False,
            'error': 'No OpenAI API key found. Use "ai setup <key>" to configure.',
            'input_text': input_text,
            'track_info': {
                'file_path': track.file_path,
                'title': track.title,
                'artist': track.artist,
                'album': track.album,
                'genre': track.genre,
                'year': track.year,
                'key': track.key,
                'bpm': track.bpm
            },
            'existing_notes': [note['note_text'] for note in notes],
            'existing_tags': [f"{tag['tag_name']} ({tag['source']})" for tag in existing_tags]
        }
    
    try:
        # Make the API call
        tags, request_metadata = analyze_track_with_ai(track, 'test_prompt')
        
        return {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'track_info': {
                'file_path': track.file_path,
                'title': track.title,
                'artist': track.artist,
                'album': track.album,
                'genre': track.genre,
                'year': track.year,
                'key': track.key,
                'bpm': track.bpm
            },
            'existing_notes': [note['note_text'] for note in notes],
            'existing_tags': [f"{tag['tag_name']} ({tag['source']})" for tag in existing_tags],
            'user_prompt': user_prompt,
            'full_input': input_text,
            'ai_output_tags': tags,
            'token_usage': {
                'prompt_tokens': request_metadata['prompt_tokens'],
                'completion_tokens': request_metadata['completion_tokens'],
                'response_time_ms': request_metadata['response_time_ms']
            }
        }
    
    except AIError as e:
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
            'track_info': {
                'file_path': track.file_path,
                'title': track.title,
                'artist': track.artist,
                'album': track.album,
                'genre': track.genre,
                'year': track.year,
                'key': track.key,
                'bpm': track.bpm
            },
            'existing_notes': [note['note_text'] for note in notes],
            'existing_tags': [f"{tag['tag_name']} ({tag['source']})" for tag in existing_tags],
            'user_prompt': user_prompt,
            'full_input': input_text
        }


def save_test_report(test_results: Dict[str, Any]) -> str:
    """Save AI test results to a report file and return the file path."""
    from .config import get_data_dir
    import time
    
    # Create reports directory
    reports_dir = Path.cwd() / 'ai-test-reports' # get_data_dir() / 'ai-test-reports'
    reports_dir.mkdir(exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_file = reports_dir / f"ai-prompt-test_{timestamp}.md"
    
    # Format the report
    report_content = f"""# AI Prompt Test Report
Generated: {test_results.get('timestamp', 'Unknown')}

## Test Status
**Success**: {test_results['success']}
"""
    
    if not test_results['success']:
        report_content += f"""
**Error**: {test_results.get('error', 'Unknown error')}
"""
    
    # Track info
    track_info = test_results.get('track_info', {})
    report_content += f"""
## Track Information
- **File**: `{track_info.get('file_path', 'Unknown')}`
- **Title**: {track_info.get('title', 'Unknown')}
- **Artist**: {track_info.get('artist', 'Unknown')}
- **Album**: {track_info.get('album', 'Unknown')}
- **Genre**: {track_info.get('genre', 'Unknown')}
- **Year**: {track_info.get('year', 'Unknown')}
- **Key**: {track_info.get('key', 'Unknown')}
- **BPM**: {track_info.get('bpm', 'Unknown')}

## Existing Data
### Notes
"""
    
    existing_notes = test_results.get('existing_notes', [])
    if existing_notes:
        for note in existing_notes:
            report_content += f"- {note}\n"
    else:
        report_content += "- None\n"
    
    report_content += "\n### Existing Tags\n"
    existing_tags = test_results.get('existing_tags', [])
    if existing_tags:
        for tag in existing_tags:
            report_content += f"- {tag}\n"
    else:
        report_content += "- None\n"
    
    # User prompt
    user_prompt = test_results.get('user_prompt', '')
    report_content += f"""
## User Prompt Configuration
```markdown
{user_prompt}
```

## Full AI Input
```
{test_results.get('full_input', 'Not available')}
```
"""
    
    if test_results['success']:
        # AI output and usage
        ai_tags = test_results.get('ai_output_tags', [])
        token_usage = test_results.get('token_usage', {})
        
        report_content += f"""
## AI Output
### Generated Tags
{', '.join(ai_tags) if ai_tags else 'None'}

### Token Usage
- **Prompt Tokens**: {token_usage.get('prompt_tokens', 'Unknown')}
- **Completion Tokens**: {token_usage.get('completion_tokens', 'Unknown')}
- **Response Time**: {token_usage.get('response_time_ms', 'Unknown')}ms
- **Estimated Cost**: ${(token_usage.get('prompt_tokens', 0) * 0.15 + token_usage.get('completion_tokens', 0) * 0.60) / 1_000_000:.6f}

## Analysis
### Tag Quality Assessment
Rate the tags from 1-5:
- **Specificity**: How specific vs generic are the tags?
- **Accuracy**: Do they match the track's actual characteristics?
- **Usefulness**: Would these help with music discovery?
- **Novelty**: Do they add new information beyond existing tags?

### Notes for Improvement
- [ ] Prompt changes needed
- [ ] Better examples needed
- [ ] Different approach required

---
*Generated by Music Minion CLI AI Test System*
"""
    
    # Write the report
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    return str(report_file)