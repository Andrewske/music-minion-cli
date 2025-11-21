"""
AI command handlers for Music Minion CLI.

Handles: ai setup, ai analyze, ai test, ai usage, ai review, ai enhance
"""

from typing import List, Tuple

from music_minion.context import AppContext
from music_minion.domain import ai
from music_minion.domain.ai import review as ai_review
from music_minion.domain.ai import prompt_enhancement
from music_minion.core import database
from music_minion.core.output import log
from music_minion.domain import library


def handle_ai_setup_command(ctx: AppContext, args: List[str]) -> Tuple[AppContext, bool]:
    """Handle ai setup command - configure OpenAI API key.

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    if not args:
        log("❌ Error: Please provide an API key. Usage: ai setup <key>", level="error")
        return ctx, True

    api_key = args[0]

    try:
        ai.store_api_key(api_key)
        log("✅ OpenAI API key stored successfully", level="info")
        log("   Key stored in ~/.config/music-minion/.env", level="info")
        log("   You can also set OPENAI_API_KEY environment variable or create .env in project root", level="info")
        log("   You can now use AI analysis features", level="info")
    except Exception as e:
        log(f"❌ Error storing API key: {e}", level="error")

    return ctx, True


def handle_ai_analyze_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle ai analyze command - analyze current track with AI.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        log("⚠️ No track is currently playing", level="warning")
        return ctx, True

    # Find current track
    current_track = None
    for track in ctx.music_tracks:
        if track.local_path == ctx.player_state.current_track:
            current_track = track
            break

    if not current_track:
        log("❌ Could not find current track information", level="error")
        return ctx, True

    log(f"🤖 Analyzing track: {library.get_display_name(current_track)}", level="info")

    try:
        result = ai.analyze_and_tag_track(current_track, 'manual_analysis')

        if result['success']:
            tags_added = result['tags_added']
            if tags_added:
                log(f"✅ Added {len(tags_added)} tags: {', '.join(tags_added)}", level="info")
            else:
                log("✅ Analysis complete - no new tags suggested", level="info")

            # Show token usage
            usage = result.get('token_usage', {})
            if usage:
                log(f"   Tokens used: {usage.get('prompt_tokens', 0)} prompt + {usage.get('completion_tokens', 0)} completion", level="info")
                log(f"   Response time: {usage.get('response_time_ms', 0)}ms", level="info")
        else:
            error_msg = result.get('error', 'Unknown error')
            log(f"❌ AI analysis failed: {error_msg}", level="error")

    except Exception as e:
        log(f"❌ Error during AI analysis: {e}", level="error")

    return ctx, True


def handle_ai_test_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle ai test command - test AI prompt with random track.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    try:
        log("🧪 Running AI prompt test with random track...", level="info")

        # Run the test
        test_results = ai.test_ai_prompt_with_random_track()

        if test_results['success']:
            # Save report
            report_file = ai.save_test_report(test_results)

            # Show summary
            track_info = test_results['track_info']
            log("✅ Test completed successfully!", level="info")
            log(f"   Track: {track_info.get('artist', 'Unknown')} - {track_info.get('title', 'Unknown')}", level="info")
            log(f"   Generated tags: {', '.join(test_results.get('ai_output_tags', []))}", level="info")

            token_usage = test_results.get('token_usage', {})
            log(f"   Tokens used: {token_usage.get('prompt_tokens', 0)} prompt + {token_usage.get('completion_tokens', 0)} completion", level="info")
            log(f"   Response time: {token_usage.get('response_time_ms', 0)}ms", level="info")

            log(f"📄 Full report saved: {report_file}", level="info")

        else:
            # Save report even for failed tests
            report_file = ai.save_test_report(test_results)
            error_msg = test_results.get('error', 'Unknown error')
            log(f"❌ Test failed: {error_msg}", level="error")
            log(f"📄 Report with input data saved: {report_file}", level="info")

        return ctx, True

    except Exception as e:
        log(f"❌ Error during AI test: {e}", level="error")
        return ctx, True


def handle_ai_usage_command(ctx: AppContext, args: List[str]) -> Tuple[AppContext, bool]:
    """Handle ai usage command - show AI usage statistics.

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
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

        log(usage_text, level="info")

        return ctx, True
    except Exception as e:
        log(f"❌ Error getting AI usage stats: {e}", level="error")
        return ctx, True


def handle_ai_review_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Handle ai review command - review tags for currently playing track.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        log("❌ No track is currently playing", level="error")
        return ctx, True

    # Find current track
    current_track = None
    for track in ctx.music_tracks:
        if track.local_path == ctx.player_state.current_track:
            current_track = track
            break

    if not current_track:
        log("❌ Could not find current track information", level="error")
        return ctx, True

    log(f"🎵 Reviewing tags for: {library.get_display_name(current_track)}", level="info")

    try:
        # Get or generate tags with reasoning
        tags_with_reasoning, is_new = ai_review.get_or_generate_tags_with_reasoning(current_track)

        if is_new:
            log("✨ Generated new tags for this track", level="info")
        else:
            log("📋 Loaded existing tags", level="info")

        log("", level="info")
        log("─" * 60, level="info")
        log("Tags with AI reasoning:", level="info")
        log("", level="info")
        for tag, reasoning in tags_with_reasoning.items():
            log(f"  • {tag}: \"{reasoning}\"", level="info")
        log("─" * 60, level="info")
        log("", level="info")
        log("💬 Entering conversation mode. Type your feedback, or 'done' to finish.", level="info")
        log("   Example: \"This is half-time, not energetic. Don't tag key.\"", level="info")
        log("", level="info")

        # Prepare track data for review mode
        track_data = {
            'local_path': str(current_track.local_path),
            'title': current_track.title,
            'artist': current_track.artist,
            'album': current_track.album,
            'genre': current_track.genre,
            'year': current_track.year,
            'bpm': current_track.bpm,
            'key': current_track.key
        }

        # Set UI action to start review mode (blessed UI will handle this)
        ctx = ctx.with_ui_action({
            'type': 'start_review_mode',
            'track_data': track_data,
            'tags_with_reasoning': tags_with_reasoning
        })

        return ctx, True

    except ai.AIError as e:
        log(f"❌ AI error: {e}", level="error")
        return ctx, True
    except Exception as e:
        log(f"❌ Unexpected error during review: {e}", level="error")
        import traceback
        traceback.print_exc()
        return ctx, True


def handle_ai_enhance_command(ctx: AppContext, args: List[str]) -> Tuple[AppContext, bool]:
    """Handle ai enhance prompt command - improve tagging prompt based on learnings.

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    # Check if subcommand is 'prompt' (optional)
    if args and args[0] != 'prompt':
        log(f"❌ Unknown enhance subcommand: '{args[0]}'. Use: ai enhance prompt", level="error")
        return ctx, True

    try:
        prompt_enhancement.enhance_prompt_interactive()
        return ctx, True

    except ai.AIError as e:
        log(f"❌ AI error: {e}", level="error")
        return ctx, True
    except Exception as e:
        log(f"❌ Unexpected error during prompt enhancement: {e}", level="error")
        import traceback
        traceback.print_exc()
        return ctx, True
