"""LLM-assisted cleanup of titles and artist credits for SoundCloud downloads.

Pipeline: extract records -> batch by shared keywords -> codex proposes edits
-> evaluate against a gold set (previously fixed library years).

Run: uv run python -m music_minion.domain.metadata_cleanup --help
"""
