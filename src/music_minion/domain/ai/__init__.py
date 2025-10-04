"""AI domain - OpenAI integration for track analysis.

This domain handles:
- OpenAI API key management
- Track analysis with AI
- AI-powered tagging
- Usage statistics and testing
- Prompt versioning and management
- Learning accumulation from tag feedback
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

from .prompt_manager import (
    get_ai_dir,
    get_prompts_dir,
    get_learnings_file,
    get_active_prompt_file,
    init_learnings_file,
    get_learnings,
    append_to_learnings_section,
    save_prompt_version,
    get_active_prompt,
    set_active_prompt,
    get_default_prompt,
    list_prompt_versions,
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
    "get_ai_dir",
    "get_prompts_dir",
    "get_learnings_file",
    "get_active_prompt_file",
    "init_learnings_file",
    "get_learnings",
    "append_to_learnings_section",
    "save_prompt_version",
    "get_active_prompt",
    "set_active_prompt",
    "get_default_prompt",
    "list_prompt_versions",
]
