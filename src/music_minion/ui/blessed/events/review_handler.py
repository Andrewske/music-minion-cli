"""Review mode handler for conversational AI tag review in blessed UI."""

from dataclasses import replace

from music_minion.context import AppContext
from music_minion.ui.blessed.state import (
    UIState, add_history_line, enter_review_confirm, exit_review_mode
)


def handle_review_input(ctx: AppContext, ui_state: UIState, user_input: str) -> tuple[AppContext, UIState]:
    """
    Handle user input in review mode.

    Args:
        ctx: Application context
        ui_state: Current UI state
        user_input: User's input text

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.domain.ai import review as ai_review
    from music_minion.domain import ai as ai_module

    review_data = ui_state.review_data
    conversation_lines = review_data.get('conversation_lines', [])

    if not user_input.strip():
        return ctx, ui_state

    # Add user input to conversation
    conversation_lines.append(f"\nUser: {user_input}")
    ui_state = add_history_line(ui_state, f"> {user_input}", 'cyan')

    # Check for "done" command
    if user_input.strip().lower() == 'done':
        ui_state = add_history_line(ui_state, "", 'white')
        ui_state = add_history_line(ui_state, "🔄 Regenerating tags based on your feedback...", 'yellow')

        # Regenerate tags
        try:
            track_data = review_data['track']
            initial_tags = review_data['initial_tags']
            conversation = '\n'.join(conversation_lines)

            # Validate track_data has required fields
            file_path_str = track_data.get('file_path')
            if not file_path_str:
                ui_state = add_history_line(ui_state, "❌ Error: Missing track file path", 'red')
                ui_state = exit_review_mode(ui_state)
                return ctx, ui_state

            # Convert track_data dict to Track object
            from music_minion.domain.library.models import Track
            from pathlib import Path
            track = Track(
                file_path=Path(file_path_str),
                title=track_data.get('title') or 'Unknown',
                artist=track_data.get('artist') or 'Unknown',
                album=track_data.get('album'),
                genre=track_data.get('genre'),
                year=track_data.get('year'),
                bpm=track_data.get('bpm'),
                key=track_data.get('key')
            )

            new_tags = ai_review.regenerate_tags_with_feedback(track, conversation, initial_tags)

            if new_tags:
                # Show preview
                ui_state = add_history_line(ui_state, "", 'white')
                ui_state = add_history_line(ui_state, "="*60, 'white')
                ui_state = add_history_line(ui_state, "📝 Updated Tags Preview:", 'green')
                ui_state = add_history_line(ui_state, "="*60, 'white')
                for tag, reasoning in new_tags.items():
                    ui_state = add_history_line(ui_state, f"  • {tag}: \"{reasoning}\"", 'white')
                ui_state = add_history_line(ui_state, "="*60, 'white')
                ui_state = add_history_line(ui_state, "", 'white')
                ui_state = add_history_line(ui_state, "💾 Save these tags? [y/n]:", 'yellow')

                # Enter confirm mode
                ui_state = enter_review_confirm(ui_state, new_tags)
            else:
                ui_state = add_history_line(ui_state, "❌ Failed to regenerate tags", 'red')
                ui_state = exit_review_mode(ui_state)

        except ai_module.AIError as e:
            ui_state = add_history_line(ui_state, f"❌ AI Error: {e}", 'red')
            ui_state = exit_review_mode(ui_state)
        except Exception as e:
            ui_state = add_history_line(ui_state, f"❌ Unexpected error: {e}", 'red')
            import traceback
            traceback.print_exc()
            ui_state = exit_review_mode(ui_state)

        return ctx, ui_state

    # Get AI response
    try:
        import openai
        import json

        api_key = ai_module.get_api_key()
        if not api_key:
            ui_state = add_history_line(ui_state, "❌ No API key configured", 'red')
            ui_state = exit_review_mode(ui_state)
            return ctx, ui_state

        client = openai.OpenAI(api_key=api_key)

        # Get learnings and track context
        learnings = ai_module.get_learnings()
        track_data = review_data['track']
        initial_tags = review_data['initial_tags']

        # Build track context
        from music_minion.core.database import get_track_by_path, get_track_notes
        track_file_path = track_data.get('file_path')
        db_track = get_track_by_path(track_file_path) if track_file_path else None
        track_notes = get_track_notes(db_track['id']) if db_track else []
        notes_text = "\n".join([note['note_text'] for note in track_notes]) if track_notes else "None"

        track_context = f"""Track Metadata:
- Artist: {track_data.get('artist', 'Unknown')}
- Title: {track_data.get('title', 'Unknown')}
- Album: {track_data.get('album', 'Unknown')}
- Genre: {track_data.get('genre', 'Unknown')}
- BPM: {track_data.get('bpm', 'Unknown')}
- Key: {track_data.get('key', 'Unknown')}
- User Notes: {notes_text}

Current Tags:
{json.dumps(initial_tags, indent=2)}
"""

        conversation_prompt = f"""{track_context}

Previous Learnings:
{learnings}

Conversation so far:
{chr(10).join(conversation_lines)}

User feedback: {user_input}

Please respond naturally to the user's feedback about the tags. If they suggest changes, acknowledge them and explain what you'll update. Be concise and helpful."""

        response = client.responses.create(
            model="gpt-4o-mini",
            instructions="You are helping a user review and improve AI-generated music tags. Have a natural conversation about tag quality, understand their feedback, and suggest improvements based on their guidance and any learnings.",
            input=conversation_prompt
        )

        ai_response = response.output_text.strip()

        # Add to conversation
        conversation_lines.append(f"AI: {ai_response}")

        # Update review data
        new_review_data = {**review_data, 'conversation_lines': conversation_lines}
        ui_state = replace(ui_state, review_data=new_review_data)

        # Show AI response in history
        ui_state = add_history_line(ui_state, "", 'white')
        ui_state = add_history_line(ui_state, f"🤖 {ai_response}", 'green')
        ui_state = add_history_line(ui_state, "", 'white')

    except ImportError as e:
        ui_state = add_history_line(ui_state, f"❌ Missing dependency: {e}", 'red')
        ui_state = add_history_line(ui_state, "Install with: pip install openai", 'yellow')
    except ai_module.AIError as e:
        ui_state = add_history_line(ui_state, f"❌ AI Error: {e}", 'red')
    except Exception as e:
        ui_state = add_history_line(ui_state, f"❌ Unexpected error: {e}", 'red')
        import traceback
        traceback.print_exc()

    return ctx, ui_state


def handle_review_confirmation(ctx: AppContext, ui_state: UIState, user_input: str) -> tuple[AppContext, UIState]:
    """
    Handle confirmation input (y/n) in review mode.

    Args:
        ctx: Application context
        ui_state: Current UI state
        user_input: User's input (y or n)

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.core.database import get_track_by_path, add_tags, get_db_connection
    from music_minion.domain.ai import review as ai_review
    from music_minion.domain import ai as ai_module

    review_data = ui_state.review_data
    user_response = user_input.strip().lower()

    ui_state = add_history_line(ui_state, f"> {user_input}", 'cyan')

    if user_response == 'y':
        # Save tags
        try:
            track_data = review_data['track']
            new_tags = review_data['new_tags']
            conversation_lines = review_data.get('conversation_lines', [])
            initial_tags = review_data['initial_tags']

            track_file_path = track_data.get('file_path')
            db_track = get_track_by_path(track_file_path)
            if not db_track:
                ui_state = add_history_line(ui_state, "❌ Track not found in database", 'red')
                ui_state = exit_review_mode(ui_state)
                return ctx, ui_state

            track_id = db_track['id']

            # Remove old AI tags
            with get_db_connection() as conn:
                conn.execute("""
                    DELETE FROM tags
                    WHERE track_id = ? AND source = 'ai'
                """, (track_id,))
                conn.commit()

            # Add new tags with reasoning
            tag_names = list(new_tags.keys())
            add_tags(track_id, tag_names, source='ai', reasoning=new_tags)

            ui_state = add_history_line(ui_state, "✅ Tags saved successfully!", 'green')

            # Extract and save learnings
            ui_state = add_history_line(ui_state, "", 'white')
            ui_state = add_history_line(ui_state, "🧠 Extracting learnings from conversation...", 'yellow')

            conversation = '\n'.join(conversation_lines)

            # Validate track_data has required fields
            file_path_str = track_data.get('file_path')
            if not file_path_str:
                ui_state = add_history_line(ui_state, "❌ Error: Missing track file path", 'red')
                ui_state = exit_review_mode(ui_state)
                return ctx, ui_state

            # Convert track_data to Track
            from music_minion.domain.library.models import Track
            from pathlib import Path
            track = Track(
                file_path=Path(file_path_str),
                title=track_data.get('title') or 'Unknown',
                artist=track_data.get('artist') or 'Unknown',
                album=track_data.get('album'),
                genre=track_data.get('genre'),
                year=track_data.get('year'),
                bpm=track_data.get('bpm'),
                key=track_data.get('key')
            )

            learnings_summary = ai_review.extract_learnings_from_conversation(
                conversation, track, initial_tags
            )

            if learnings_summary:
                ai_module.append_to_learnings_section("Rules - Don't Tag These", learnings_summary)
                ui_state = add_history_line(ui_state, "✅ Learnings saved!", 'green')
            else:
                ui_state = add_history_line(ui_state, "⚠️  Could not extract learnings automatically", 'yellow')

        except ai_module.AIError as e:
            ui_state = add_history_line(ui_state, f"❌ AI Error saving tags: {e}", 'red')
        except Exception as e:
            ui_state = add_history_line(ui_state, f"❌ Unexpected error saving tags: {e}", 'red')
            import traceback
            traceback.print_exc()

        ui_state = exit_review_mode(ui_state)

    elif user_response == 'n':
        ui_state = add_history_line(ui_state, "❌ Tags not saved", 'yellow')
        ui_state = exit_review_mode(ui_state)

    else:
        ui_state = add_history_line(ui_state, "Please type 'y' or 'n'", 'yellow')

    return ctx, ui_state
