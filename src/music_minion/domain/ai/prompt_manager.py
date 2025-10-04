"""
Prompt and learning management for AI tag review system.

Manages:
- Prompt versioning and storage
- Learning accumulation and categorization
- Prompt enhancement with feedback
"""

from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

from music_minion.core.config import get_config_dir


def get_ai_dir() -> Path:
    """Get the AI configuration directory."""
    ai_dir = get_config_dir() / "ai"
    ai_dir.mkdir(parents=True, exist_ok=True)
    return ai_dir


def get_prompts_dir() -> Path:
    """Get the prompts directory."""
    prompts_dir = get_ai_dir() / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    return prompts_dir


def get_learnings_file() -> Path:
    """Get the learnings markdown file path."""
    return get_ai_dir() / "learnings.md"


def get_active_prompt_file() -> Path:
    """Get the active prompt file path."""
    return get_prompts_dir() / "active.txt"


def create_default_learnings() -> str:
    """Create default learnings markdown structure."""
    return """# Music Minion Tag Learnings

Last updated: {timestamp}

## Rules - Don't Tag These
<!-- Things that should NOT be tagged because they're redundant or unhelpful -->

## Vocabulary - Approved Terms
<!-- Tags that work well and should be used more -->

## Vocabulary - Avoid These Terms
<!-- Tags that are too vague or problematic -->

## Genre-Specific Guidance
<!-- Special instructions for specific genres -->

## Examples - Good Tags
<!-- Examples of well-tagged tracks -->

## Examples - Bad Tags
<!-- Examples of poorly tagged tracks to avoid -->
""".format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def init_learnings_file() -> None:
    """Initialize the learnings file if it doesn't exist."""
    learnings_file = get_learnings_file()
    if not learnings_file.exists():
        learnings_file.write_text(create_default_learnings())


def get_learnings() -> str:
    """Get current learnings content."""
    learnings_file = get_learnings_file()
    if not learnings_file.exists():
        init_learnings_file()
    return learnings_file.read_text()


def append_to_learnings_section(section: str, content: str) -> None:
    """Append content to a specific section in learnings.

    Args:
        section: Section header (e.g., "Rules - Don't Tag These")
        content: Content to append under that section
    """
    learnings_file = get_learnings_file()
    if not learnings_file.exists():
        init_learnings_file()

    current_content = learnings_file.read_text()
    lines = current_content.split('\n')

    # Find the section
    section_header = f"## {section}"
    section_index = None
    for i, line in enumerate(lines):
        if line.strip() == section_header:
            section_index = i
            break

    if section_index is None:
        # Section doesn't exist, append it
        current_content += f"\n\n{section_header}\n{content}\n"
    else:
        # Find next section or end of file
        next_section_index = len(lines)
        for i in range(section_index + 1, len(lines)):
            if lines[i].strip().startswith("## "):
                next_section_index = i
                break

        # Insert content before next section
        lines.insert(next_section_index, content)
        current_content = '\n'.join(lines)

    # Update timestamp
    current_content = current_content.replace(
        "Last updated:",
        f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nLast updated:"
    ).replace("Last updated:\n\nLast updated:", "Last updated:")

    learnings_file.write_text(current_content)


def save_prompt_version(prompt: str, version_note: Optional[str] = None) -> str:
    """Save a new prompt version.

    Args:
        prompt: The prompt text
        version_note: Optional note about this version

    Returns:
        Path to the saved prompt file
    """
    prompts_dir = get_prompts_dir()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    version_file = prompts_dir / f"v-{timestamp}.txt"

    # Add metadata header
    content = f"""# Prompt Version: {timestamp}
# Note: {version_note or 'No note provided'}
# Created: {datetime.now().isoformat()}

{prompt}
"""

    version_file.write_text(content)
    return str(version_file)


def get_active_prompt() -> str:
    """Get the currently active prompt."""
    active_file = get_active_prompt_file()

    # If no active file, check for legacy ai-prompt.md
    if not active_file.exists():
        legacy_file = get_config_dir() / "ai-prompt.md"
        if legacy_file.exists():
            # Migrate legacy prompt to new system
            prompt = legacy_file.read_text().strip()
            set_active_prompt(prompt, "Migrated from legacy ai-prompt.md")
            return prompt

    if active_file.exists():
        content = active_file.read_text()
        # Skip metadata lines starting with #
        lines = [line for line in content.split('\n') if not line.strip().startswith('#')]
        return '\n'.join(lines).strip()

    # Return default if nothing exists
    return get_default_prompt()


def set_active_prompt(prompt: str, note: Optional[str] = None) -> None:
    """Set the active prompt and save as version.

    Args:
        prompt: The prompt text
        note: Optional version note
    """
    # Save as version
    save_prompt_version(prompt, note)

    # Update active file
    active_file = get_active_prompt_file()
    content = f"""# Active Prompt
# Last updated: {datetime.now().isoformat()}
# Note: {note or 'Updated prompt'}

{prompt}
"""
    active_file.write_text(content)


def get_default_prompt() -> str:
    """Get the default AI tagging prompt."""
    return """# AI Music Analysis Instructions

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


def list_prompt_versions() -> List[Dict[str, str]]:
    """List all prompt versions.

    Returns:
        List of dicts with 'file', 'timestamp', 'note' keys
    """
    prompts_dir = get_prompts_dir()
    versions = []

    for file in sorted(prompts_dir.glob("v-*.txt"), reverse=True):
        # Parse metadata from file
        content = file.read_text()
        lines = content.split('\n')

        timestamp = ""
        note = ""
        for line in lines[:5]:  # Check first few lines
            if line.startswith("# Prompt Version:"):
                timestamp = line.split(":", 1)[1].strip()
            elif line.startswith("# Note:"):
                note = line.split(":", 1)[1].strip()

        versions.append({
            'file': str(file),
            'timestamp': timestamp,
            'note': note
        })

    return versions
