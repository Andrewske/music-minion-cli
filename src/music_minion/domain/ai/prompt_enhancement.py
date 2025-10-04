"""
Prompt enhancement system for evolving AI tagging based on accumulated learnings.

Analyzes learnings, proposes prompt improvements, and validates with test tracks.
"""

import json
import random
from typing import Dict, List, Tuple, Optional, Any

from music_minion.domain.library import Track
from music_minion.core.database import get_all_tracks, db_track_to_library_track, get_track_tags
from .client import analyze_track_with_ai, AIError, get_api_key
from .prompt_manager import (
    get_active_prompt, get_learnings, set_active_prompt,
    save_prompt_version, get_default_prompt
)


def propose_prompt_improvements(current_prompt: str, learnings: str) -> Optional[Tuple[str, str]]:
    """Propose improvements to the current prompt based on learnings.

    Args:
        current_prompt: Current active prompt
        learnings: Accumulated learnings markdown

    Returns:
        Tuple of (new_prompt, explanation) or None if failed
    """
    try:
        api_key = get_api_key()
        if not api_key:
            raise AIError("No API key configured")

        import openai
        client = openai.OpenAI(api_key=api_key)

        enhancement_prompt = f"""You are helping improve an AI music tagging system's prompt based on user feedback.

Current Prompt:
```
{current_prompt}
```

Accumulated Learnings from User Feedback:
```markdown
{learnings}
```

Task: Propose an improved version of the prompt that incorporates the learnings.

Focus on:
1. Adding rules from "Don't Tag These" section
2. Incorporating approved vocabulary
3. Avoiding problematic terms
4. Adding genre-specific guidance if present

Return a JSON object with:
- "improved_prompt": the full improved prompt text
- "changes_summary": bullet list of key changes made

Example format:
{{
    "improved_prompt": "# AI Music Analysis Instructions\\n\\n...",
    "changes_summary": "- Added rule: Don't tag key/BPM (already in metadata)\\n- Emphasized specific tempo descriptors\\n- Avoid vague terms like 'energetic'"
}}
"""

        response = client.responses.create(
            model="gpt-4o-mini",
            instructions="Improve the AI music tagging prompt based on user learnings. Return only valid JSON with improved_prompt and changes_summary.",
            input=enhancement_prompt
        )

        output_text = response.output_text.strip()

        # Parse JSON
        if '```json' in output_text:
            json_start = output_text.find('{')
            json_end = output_text.rfind('}') + 1
            output_text = output_text[json_start:json_end]

        result = json.loads(output_text)

        return result['improved_prompt'], result['changes_summary']

    except Exception as e:
        print(f"❌ Error proposing improvements: {e}")
        return None


def test_prompt_on_tracks(prompt_text: str, num_tracks: int = 3) -> List[Dict[str, Any]]:
    """Test a prompt on random tracks that already have tags.

    Args:
        prompt_text: Prompt to test (not used directly, but for context)
        num_tracks: Number of tracks to test on

    Returns:
        List of test results with track info and generated tags
    """
    # Get all tracks that have AI tags
    all_tracks = get_all_tracks()
    tracks_with_ai_tags = []

    for db_track in all_tracks:
        tags = get_track_tags(db_track['id'], include_blacklisted=False)
        if any(tag['source'] == 'ai' for tag in tags):
            tracks_with_ai_tags.append(db_track)

    if not tracks_with_ai_tags:
        print("⚠️  No tracks with existing AI tags found. Using random tracks instead.")
        tracks_with_ai_tags = all_tracks

    if len(tracks_with_ai_tags) < num_tracks:
        num_tracks = len(tracks_with_ai_tags)

    # Select random tracks
    selected_tracks = random.sample(tracks_with_ai_tags, num_tracks)

    results = []

    for db_track in selected_tracks:
        track = db_track_to_library_track(db_track)

        # Get existing tags
        existing_tags = get_track_tags(db_track['id'], include_blacklisted=False)
        ai_tags = [tag for tag in existing_tags if tag['source'] == 'ai']

        # Generate new tags with the (implicitly active) prompt
        try:
            new_tag_list, _, new_reasoning = analyze_track_with_ai(
                track, 'prompt_test', return_reasoning=True
            )

            results.append({
                'track': {
                    'artist': track.artist,
                    'title': track.title,
                    'genre': track.genre,
                    'bpm': track.bpm,
                    'key': track.key
                },
                'old_tags': {tag['tag_name']: tag.get('reasoning', 'No reasoning') for tag in ai_tags},
                'new_tags': new_reasoning or {tag: 'Generated' for tag in new_tag_list},
                'success': True
            })

        except Exception as e:
            results.append({
                'track': {
                    'artist': track.artist,
                    'title': track.title
                },
                'old_tags': {tag['tag_name']: tag.get('reasoning', 'No reasoning') for tag in ai_tags},
                'new_tags': {},
                'success': False,
                'error': str(e)
            })

    return results


def display_prompt_comparison(current_prompt: str, new_prompt: str, changes_summary: str,
                               test_results: List[Dict[str, Any]]) -> None:
    """Display a side-by-side comparison of prompts and test results.

    Args:
        current_prompt: Current active prompt
        new_prompt: Proposed new prompt
        changes_summary: Summary of changes
        test_results: Results from testing the new prompt
    """
    print("\n" + "="*70)
    print("📝 PROMPT ENHANCEMENT PROPOSAL")
    print("="*70)

    print("\n🔄 Proposed Changes:")
    print(changes_summary)

    print("\n" + "-"*70)
    print("📊 Testing Results on 3 Tracks:")
    print("-"*70)

    for i, result in enumerate(test_results, 1):
        track_info = result['track']
        print(f"\n{i}. {track_info.get('artist', 'Unknown')} - {track_info.get('title', 'Unknown')}")
        if track_info.get('genre'):
            print(f"   Genre: {track_info['genre']}, BPM: {track_info.get('bpm', 'N/A')}, Key: {track_info.get('key', 'N/A')}")

        if not result['success']:
            print(f"   ❌ Error: {result.get('error', 'Unknown')}")
            continue

        old_tags = result['old_tags']
        new_tags = result['new_tags']

        print("\n   OLD TAGS:")
        if old_tags:
            for tag, reasoning in old_tags.items():
                print(f"     • {tag}: \"{reasoning}\"")
        else:
            print("     (none)")

        print("\n   NEW TAGS:")
        if new_tags:
            for tag, reasoning in new_tags.items():
                print(f"     • {tag}: \"{reasoning}\"")
        else:
            print("     (none)")

        print()

    print("="*70)


def enhance_prompt_interactive() -> bool:
    """Run interactive prompt enhancement workflow.

    Returns:
        True if prompt was enhanced and saved, False otherwise
    """
    print("\n🧠 AI Prompt Enhancement")
    print("="*60)

    # Get current prompt and learnings
    current_prompt = get_active_prompt()
    if not current_prompt:
        current_prompt = get_default_prompt()

    learnings = get_learnings()

    # Check if there are any learnings
    if "<!-- Things that should NOT be tagged" in learnings and "<!--" in learnings:
        print("⚠️  No learnings accumulated yet. Use 'ai review' to build up feedback first.")
        return False

    print("📖 Analyzing accumulated learnings...")

    # Propose improvements
    proposal = propose_prompt_improvements(current_prompt, learnings)
    if not proposal:
        print("❌ Failed to generate prompt improvements")
        return False

    new_prompt, changes_summary = proposal

    # Temporarily save new prompt to test it
    original_active = current_prompt
    set_active_prompt(new_prompt, "Testing proposed improvements")

    print("🧪 Testing new prompt on 3 random tracks...")
    test_results = test_prompt_on_tracks(new_prompt, num_tracks=3)

    # Display comparison
    display_prompt_comparison(current_prompt, new_prompt, changes_summary, test_results)

    # Ask for approval
    approve = input("\n💾 Apply these prompt improvements? [y/n]: ").strip().lower()

    if approve == 'y':
        # Save as new version
        set_active_prompt(new_prompt, f"Applied learnings: {changes_summary[:100]}")
        print("✅ Prompt updated successfully!")
        print(f"📁 New prompt saved to: {save_prompt_version(new_prompt, changes_summary)}")
        return True
    else:
        # Restore original
        set_active_prompt(original_active, "Reverted - proposal rejected")
        print("❌ Prompt changes rejected. Keeping current prompt.")
        return False
