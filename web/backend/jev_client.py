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
from typing import Any, Final, Literal

import httpx

DEFAULT_BASE_URL = "https://openrouter.ai/api"
DEFAULT_MODEL_ID = "jev-latest"
SYSTEMONE_PATH = "/v1/systemone"

# An answer object that carries no Noul value at all (e.g. {"type": "noul"}).
# Unlike an invalid value it is likely transient, so callers may ask again.
INCOMPLETE: Final = "incomplete"

# A probability, None for an explicitly invalid value, or INCOMPLETE.
NoulAnswer = float | None | Literal["incomplete"]


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


def valid_probability(value: Any) -> float | None:
    """`value` as a probability, or None unless it is a finite number in [0, 1].

    JSON booleans, strings, NaN and Infinity are all rejected: a malformed
    answer must never read as a confident one. The range check runs before
    any float conversion, so a huge JSON integer is rejected, not overflowed.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not 0 <= value <= 1:  # False for NaN
        return None
    return float(value)


def _answers_object(payload: Any) -> dict:
    answers = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(answers, dict):
        # ValueError, not TypeError: callers count it as a failed batch.
        raise ValueError(  # noqa: TRY004
            f"Jev response has no answers object (got {type(answers).__name__})"
        )
    return answers


def _answer_noul(answer: Any) -> float | None:
    return valid_probability(answer.get("noul")) if isinstance(answer, dict) else None


def _batch_answer(answer: Any) -> NoulAnswer:
    """INCOMPLETE when the answer has no Noul value, else `_answer_noul`."""
    if not isinstance(answer, dict) or answer.get("noul") is None:
        return INCOMPLETE
    return _answer_noul(answer)


def _parse_noul_response(payload: dict, fallback_model: str) -> JevPrediction:
    """Pull the single Noul answer out of a systemone response."""
    answer = _answers_object(payload).get("keep")
    if answer is None:
        raise ValueError(f"Jev response has no 'keep' answer: {list(payload.keys())}")
    probability = _answer_noul(answer)
    if probability is None:
        raise ValueError(
            f"Jev 'keep' answer is not a probability in [0, 1]: {answer!r}"
        )
    return JevPrediction(
        probability=probability,
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


def _parse_noul_answers(payload: Any, question_ids: list[str]) -> dict[str, NoulAnswer]:
    """Noul value per answered question id.

    Questions Jev didn't answer are left out; an answer with no Noul value
    is INCOMPLETE; a value that isn't a finite probability in [0, 1] maps to
    None so callers can record it as invalid. A response without an answers
    object is a ValueError.
    """
    answers = _answers_object(payload)
    return {
        qid: _batch_answer(answers[qid])
        for qid in question_ids
        if answers.get(qid) is not None
    }


def ask_nouls(
    config: JevConfig, state: str, questions: dict[str, str], timeout_s: float = 30.0
) -> dict[str, NoulAnswer]:
    """Ask several Noul questions about one state in a single call.

    Used to batch tracks: each question id names one track. Raises on HTTP
    errors; an empty answer set is a ValueError so callers count a failure.
    Malformed answers come back as None or INCOMPLETE (see
    `_parse_noul_answers`).
    """
    response = httpx.post(
        f"{config.base_url}{SYSTEMONE_PATH}",
        json={
            "model": config.model_id,
            "state": state,
            "questions": {
                qid: {"type": "noul", "instructions": text}
                for qid, text in questions.items()
            },
        },
        headers={"Authorization": f"Bearer {config.api_key}"},
        timeout=timeout_s,
    )
    response.raise_for_status()
    nouls = _parse_noul_answers(response.json(), list(questions))
    if not nouls:
        raise ValueError(f"Jev answered none of {len(questions)} questions")
    return nouls
