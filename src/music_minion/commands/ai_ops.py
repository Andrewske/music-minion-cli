"""
AI command handlers for Music Minion CLI.

Handles: ai setup, ai analyze, ai test, ai usage
"""

from typing import List

from .. import ai
from ..core import database
from .. import library


def get_player_state():
    """Get current player state from main module."""
    from .. import main
    return main.current_player_state


def get_music_tracks():
    """Get music tracks from main module."""
    from .. import main
    return main.music_tracks


def handle_ai_setup_command(args: List[str]) -> bool:
    """Handle ai setup command - configure OpenAI API key."""
    if not args:
        print("Error: Please provide an API key. Usage: ai setup <key>")
        return True

    api_key = args[0]

    try:
        ai.store_api_key(api_key)
        print("✅ OpenAI API key stored successfully")
        print("   Key stored in ~/.config/music-minion/.env")
        print("   You can also set OPENAI_API_KEY environment variable or create .env in project root")
        print("   You can now use AI analysis features")
    except Exception as e:
        print(f"❌ Error storing API key: {e}")

    return True


def handle_ai_analyze_command() -> bool:
    """Handle ai analyze command - analyze current track with AI."""
    current_player_state = get_player_state()
    music_tracks = get_music_tracks()

    if not current_player_state.current_track:
        print("No track is currently playing")
        return True

    # Find current track
    current_track = None
    for track in music_tracks:
        if track.file_path == current_player_state.current_track:
            current_track = track
            break

    if not current_track:
        print("Could not find current track information")
        return True

    print(f"🤖 Analyzing track: {library.get_display_name(current_track)}")

    try:
        result = ai.analyze_and_tag_track(current_track, 'manual_analysis')

        if result['success']:
            tags_added = result['tags_added']
            if tags_added:
                print(f"✅ Added {len(tags_added)} tags: {', '.join(tags_added)}")
            else:
                print("✅ Analysis complete - no new tags suggested")

            # Show token usage
            usage = result.get('token_usage', {})
            if usage:
                print(f"   Tokens used: {usage.get('prompt_tokens', 0)} prompt + {usage.get('completion_tokens', 0)} completion")
                print(f"   Response time: {usage.get('response_time_ms', 0)}ms")
        else:
            error_msg = result.get('error', 'Unknown error')
            print(f"❌ AI analysis failed: {error_msg}")

    except Exception as e:
        print(f"❌ Error during AI analysis: {e}")

    return True


def handle_ai_test_command() -> bool:
    """Handle ai test command - test AI prompt with random track."""
    try:
        print("🧪 Running AI prompt test with random track...")

        # Run the test
        test_results = ai.test_ai_prompt_with_random_track()

        if test_results['success']:
            # Save report
            report_file = ai.save_test_report(test_results)

            # Show summary
            track_info = test_results['track_info']
            print(f"✅ Test completed successfully!")
            print(f"   Track: {track_info.get('artist', 'Unknown')} - {track_info.get('title', 'Unknown')}")
            print(f"   Generated tags: {', '.join(test_results.get('ai_output_tags', []))}")

            token_usage = test_results.get('token_usage', {})
            print(f"   Tokens used: {token_usage.get('prompt_tokens', 0)} prompt + {token_usage.get('completion_tokens', 0)} completion")
            print(f"   Response time: {token_usage.get('response_time_ms', 0)}ms")

            print(f"📄 Full report saved: {report_file}")

        else:
            # Save report even for failed tests
            report_file = ai.save_test_report(test_results)
            error_msg = test_results.get('error', 'Unknown error')
            print(f"❌ Test failed: {error_msg}")
            print(f"📄 Report with input data saved: {report_file}")

        return True

    except Exception as e:
        print(f"❌ Error during AI test: {e}")
        return True


def handle_ai_usage_command(args: List[str]) -> bool:
    """Handle ai usage command - show AI usage statistics."""
    try:
        if args and args[0] == 'today':
            stats = database.get_ai_usage_stats(days=1)
            usage_text = ai.format_usage_stats(stats, "Today's")
        elif args and args[0] == 'month':
            stats = database.get_ai_usage_stats(days=30)
            usage_text = ai.format_usage_stats(stats, "Last 30 Days")
        else:
            stats = database.get_ai_usage_stats()
            usage_text = ai.format_usage_stats(stats, "Total")

        print(usage_text)

        return True
    except Exception as e:
        print(f"❌ Error getting AI usage stats: {e}")
        return True
