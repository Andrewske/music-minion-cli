"""
AI Tag Review System - Conversational tag feedback and learning.

Provides interactive review of AI-generated tags with reasoning,
allowing users to provide feedback and improve the tagging system over time.
"""

import json
from typing import Optional

from music_minion.domain.library import Track, get_track_id_from_track
from music_minion.core.database import get_track_by_path, get_track_tags
from music_minion.core.output import log
from .client import analyze_track_with_ai, AIError, get_api_key
from .prompt_manager import get_learnings


def get_or_generate_tags_with_reasoning(track: Track) -> tuple[dict[str, str], bool]:
    """Get existing tags with reasoning or generate new ones.

    Args:
        track: Track to get/generate tags for

    Returns:
        Tuple of (tags_with_reasoning_dict, is_newly_generated)
    """
    # Get track from database (multi-source support)
    track_id = get_track_id_from_track(track)
    if not track_id:
        raise ValueError("Track not found in database")

    # Get existing AI tags
    existing_tags = get_track_tags(track_id, include_blacklisted=False)
    ai_tags = [tag for tag in existing_tags if tag["source"] == "ai"]

    # If we have tags with reasoning, return them
    if ai_tags and any(tag.get("reasoning") for tag in ai_tags):
        tags_with_reasoning = {
            tag["tag_name"]: tag.get("reasoning", "No reasoning provided")
            for tag in ai_tags
        }
        return tags_with_reasoning, False

    # Otherwise, generate new tags
    tags_list, _, reasoning = analyze_track_with_ai(
        track, "review_mode", return_reasoning=True
    )

    if not reasoning:
        # Fallback: create reasoning dict
        reasoning = {tag: "Generated tag" for tag in tags_list}

    return reasoning, True


def extract_learnings_from_conversation(
    conversation: str, track: Track, initial_tags: dict[str, str]
) -> Optional[str]:
    """Extract structured learnings from a tag review conversation.

    Args:
        conversation: Full conversation text
        track: Track that was reviewed
        initial_tags: Initial tags that were reviewed

    Returns:
        Extracted learnings summary or None if extraction failed
    """
    try:
        api_key = get_api_key()
        if not api_key:
            return None

        import openai

        client = openai.OpenAI(api_key=api_key)

        extraction_prompt = f"""Based on this tag review conversation, extract key learnings for improving future tagging.

Conversation:
{conversation}

Extract learnings in these categories:
1. Rules (things to NOT tag, like "don't tag key - it's in metadata")
2. Good vocabulary (tags that worked well)
3. Bad vocabulary (tags to avoid, like "too vague")
4. Specific guidance (genre-specific or situational rules)

Return a JSON object with these keys: "rules", "good_vocab", "bad_vocab", "guidance"
Each value should be a list of strings.

Example:
{{
    "rules": ["Don't tag key - already in metadata", "Don't tag BPM numbers"],
    "good_vocab": ["half-time: slower groove feel", "filthy: aggressive distorted bass"],
    "bad_vocab": ["energetic: too vague without context"],
    "guidance": ["For electronic music, focus on bass character and build patterns"]
}}
"""

        response = client.responses.create(
            model="gpt-4o-mini",
            instructions="Extract structured learnings from a music tag review conversation. Return only valid JSON with the specified structure.",
            input=extraction_prompt,
        )

        learnings_json = response.output_text.strip()

        # Parse JSON
        if "```json" in learnings_json:
            json_start = learnings_json.find("{")
            json_end = learnings_json.rfind("}") + 1
            learnings_json = learnings_json[json_start:json_end]

        learnings_data = json.loads(learnings_json)

        # Format as markdown sections
        summary_lines = []

        if learnings_data.get("rules"):
            for rule in learnings_data["rules"]:
                summary_lines.append(f"- {rule}")

        summary = "\n".join(summary_lines) if summary_lines else None

        return summary

    except Exception as e:
        log(f"⚠️  Warning: Could not extract learnings: {e}", level="warning")
        return None


def regenerate_tags_with_feedback(
    track: Track, conversation: str, initial_tags: dict[str, str]
) -> Optional[dict[str, str]]:
    """Regenerate tags based on conversation feedback.

    Args:
        track: Track to re-tag
        conversation: Full conversation history
        initial_tags: Original tags

    Returns:
        New tags with reasoning, or None if regeneration failed
    """
    try:
        api_key = get_api_key()
        if not api_key:
            raise AIError("No API key configured")

        import openai
        from music_minion.core.database import get_track_notes

        client = openai.OpenAI(api_key=api_key)

        # Get track metadata
        db_track = get_track_by_path(track.local_path)
        track_notes = get_track_notes(db_track["id"]) if db_track else []
        notes_text = (
            "\n".join([note["note_text"] for note in track_notes])
            if track_notes
            else "None"
        )

        learnings = get_learnings()

        regeneration_prompt = f"""Based on this conversation about improving tags, generate FINAL IMPROVED tags for this track.

Track Info:
- Artist: {track.artist}
- Title: {track.title}
- Album: {track.album or "Unknown"}
- Genre: {track.genre or "Unknown"}
- BPM: {track.bpm or "Unknown"}
- Key: {track.key or "Unknown"}
- User Notes: {notes_text}

Previous Tags (being improved):
{json.dumps(initial_tags, indent=2)}

Conversation with user feedback:
{conversation}

Learnings to apply:
{learnings}

Generate 3-6 improved tags as JSON with tag:reasoning pairs.
Apply all the user's feedback from the conversation.

Example format:
{{
    "half-time": "Slower groove feel despite BPM",
    "chill": "Relaxed, downtempo mood",
    "synth-heavy": "Dominant synthesizer throughout"
}}
"""

        response = client.responses.create(
            model="gpt-4o-mini",
            instructions="Generate improved music tags based on user feedback. Return only valid JSON with tag:reasoning pairs. Apply all learnings and feedback.",
            input=regeneration_prompt,
        )

        output_text = response.output_text.strip()

        # Parse JSON
        if "```json" in output_text:
            json_start = output_text.find("{")
            json_end = output_text.rfind("}") + 1
            output_text = output_text[json_start:json_end]

        new_tags = json.loads(output_text)

        # Normalize to lowercase keys
        new_tags = {tag.lower(): reasoning for tag, reasoning in new_tags.items()}

        return new_tags

    except Exception as e:
        log(f"❌ Error regenerating tags: {e}", level="error")
        return None
