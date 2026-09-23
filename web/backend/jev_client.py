"""Thin HTTP client for the TypeSafe Jev System One API.

Provider-agnostic: endpoint, key, and model id all come from the
environment (JEV_BASE_URL / JEV_API_KEY / JEV_MODEL_ID), so switching
between OpenRouter (the default; JEV_API_KEY falls back to
OPENROUTER_API_KEY) and the direct TypeSafe API is an env-only change.
One Noul question per call; callers own retries.

Verified request/response shape (OpenRouter /api/v1/systemone, 2026-09-23):
request  {"model", "state", "questions": {"<id>": {"type", "instructions"}}}
response {"model", "answers": {"<id>": {"type": "noul", "noul": 0.99}}, "usage"}
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import httpx

DEFAULT_BASE_URL = "https://openrouter.ai/api"
DEFAULT_MODEL_ID = "jev-latest"
SYSTEMONE_PATH = "/v1/systemone"


@dataclass(frozen=True)
class JevConfig:
    base_url: str
    api_key: str
    model_id: str


@dataclass(frozen=True)
class JevPrediction:
    probability: float
    confidence: float | None
    model_id: str
    raw: dict


def _load_env_files() -> None:
    """Load .env from the project root and the XDG config dir (best effort)."""
    try:
        from dotenv import load_dotenv

        from music_minion.core.config import get_config_dir

        for env_file in (Path.cwd() / ".env", get_config_dir() / ".env"):
            if env_file.exists():
                load_dotenv(env_file)
    except ImportError:
        pass


def get_jev_config() -> JevConfig | None:
    """Resolve Jev credentials from the environment; None when unconfigured."""
    if not os.getenv("JEV_API_KEY") and not os.getenv("OPENROUTER_API_KEY"):
        _load_env_files()
    api_key = os.getenv("JEV_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None
    return JevConfig(
        base_url=os.getenv("JEV_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        api_key=api_key,
        model_id=os.getenv("JEV_MODEL_ID", DEFAULT_MODEL_ID),
    )


def _build_noul_request(config: JevConfig, state: str, question: str) -> dict:
    return {
        "model": config.model_id,
        "state": state,
        "questions": {"keep": {"type": "noul", "instructions": question}},
    }


def _parse_noul_response(payload: dict, fallback_model: str) -> JevPrediction:
    """Pull the single Noul answer out of a systemone response."""
    answer = (payload.get("answers") or {}).get("keep")
    if answer is None:
        raise ValueError(f"Jev response has no 'keep' answer: {list(payload.keys())}")
    noul = answer.get("noul")
    if noul is None:
        raise ValueError(f"Jev answer has no noul value: {list(answer.keys())}")
    return JevPrediction(
        probability=float(noul),
        confidence=answer.get("confidence"),
        model_id=payload.get("model", fallback_model),
        raw=payload,
    )


def ask_noul(
    config: JevConfig, state: str, question: str, timeout_s: float = 10.0
) -> JevPrediction:
    """Ask Jev a single Noul question about `state`; raises on HTTP errors."""
    response = httpx.post(
        f"{config.base_url}{SYSTEMONE_PATH}",
        json=_build_noul_request(config, state, question),
        headers={"Authorization": f"Bearer {config.api_key}"},
        timeout=timeout_s,
    )
    response.raise_for_status()
    return _parse_noul_response(response.json(), config.model_id)
