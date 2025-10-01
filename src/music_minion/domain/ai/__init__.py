"""AI domain - OpenAI integration for track analysis.

This domain handles:
- OpenAI API key management
- Track analysis with AI
- AI-powered tagging
- Usage statistics and testing
"""

from .client import (
    AIError,
    get_api_key,
    store_api_key,
    get_user_prompt,
    build_analysis_input,
    analyze_track_with_ai,
    analyze_and_tag_track,
    format_usage_stats,
    test_ai_prompt_with_random_track,
    save_test_report,
)

__all__ = [
    "AIError",
    "get_api_key",
    "store_api_key",
    "get_user_prompt",
    "build_analysis_input",
    "analyze_track_with_ai",
    "analyze_and_tag_track",
    "format_usage_stats",
    "test_ai_prompt_with_random_track",
    "save_test_report",
]
