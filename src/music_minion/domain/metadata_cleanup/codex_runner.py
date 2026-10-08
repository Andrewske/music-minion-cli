"""Send batches to `codex exec` (ChatGPT subscription) and collect structured edits."""

import json
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

PACKAGE_DIR = Path(__file__).parent
GUIDELINES_PATH = PACKAGE_DIR / "guidelines.md"
SCHEMA_PATH = PACKAGE_DIR / "output-schema.json"
_DESCRIPTION_LIMIT = 800


@dataclass(frozen=True)
class CodexSettings:
    model: str = "gpt-6-luna"
    reasoning: str = "medium"
    web_search: bool = True
    timeout_s: int = 600


def prompt_record(record: dict[str, Any]) -> dict[str, Any]:
    """Drop empty fields and cap long descriptions to keep prompts small."""
    sc = dict(record.get("soundcloud") or {})
    if "description" in sc:
        sc["description"] = sc["description"][:_DESCRIPTION_LIMIT]
    view = {
        "id": record["id"],
        "filename": record["filename"],
        "soundcloud": sc or None,
    }
    view["file_tags"] = record.get("file_tags")
    return {key: value for key, value in view.items() if value}


def build_prompt(guidelines: str, batch: list[dict[str, Any]]) -> str:
    tracks = json.dumps([prompt_record(r) for r in batch], ensure_ascii=False, indent=1)
    return (
        f"{guidelines}\n\n## Tracks\nReturn exactly {len(batch)} results, "
        f"one per id. Do not run shell commands.\n\n{tracks}\n"
    )


def _codex_command(settings: CodexSettings, out_path: Path) -> list[str]:
    search = "live" if settings.web_search else "disabled"
    return [
        "codex", "exec", "-m", settings.model,
        "-c", f'model_reasoning_effort="{settings.reasoning}"',
        "-c", f'web_search="{search}"',
        "--ephemeral", "--skip-git-repo-check", "-s", "read-only",
        "--output-schema", str(SCHEMA_PATH), "-o", str(out_path), "-",
    ]  # fmt: skip


def run_batch(prompt: str, settings: CodexSettings) -> list[dict[str, Any]]:
    """Run one codex call in an empty temp dir; raises on failure."""
    with tempfile.TemporaryDirectory(prefix="mm-cleanup-") as tmp:
        out_path = Path(tmp) / "out.json"
        result = subprocess.run(
            _codex_command(settings, out_path),
            input=prompt, cwd=tmp, capture_output=True, text=True,
            timeout=settings.timeout_s,
        )  # fmt: skip
        if result.returncode != 0 or not out_path.exists():
            raise RuntimeError(
                f"codex exec failed (exit {result.returncode}): {result.stderr[-1500:]}"
            )
        return json.loads(out_path.read_text())["tracks"]


def _run_one(
    index: int, batch: list[dict], guidelines: str, settings: CodexSettings
) -> dict:
    started = time.monotonic()
    ids = [record["id"] for record in batch]
    try:
        tracks = run_batch(build_prompt(guidelines, batch), settings)
        error = None
    except (
        RuntimeError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        KeyError,
    ) as exc:
        logger.exception(
            f"Batch {index} failed ({len(batch)} tracks, first id {ids[0]})"
        )
        tracks, error = [], str(exc)
    seconds = round(time.monotonic() - started, 1)
    logger.info(f"Batch {index}: {len(tracks)}/{len(batch)} results in {seconds}s")
    return {
        "batch": index,
        "ids": ids,
        "tracks": tracks,
        "error": error,
        "seconds": seconds,
    }


def run_batches(
    batches: list[list[dict]], settings: CodexSettings, workers: int = 3
) -> list[dict[str, Any]]:
    """Run batches concurrently; failures are recorded per batch, not raised."""
    guidelines = GUIDELINES_PATH.read_text()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_run_one, i, batch, guidelines, settings)
            for i, batch in enumerate(batches)
        ]
        return [future.result() for future in futures]
