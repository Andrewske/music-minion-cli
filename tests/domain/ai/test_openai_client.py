"""Tests for the shared OpenAI client helper and AI error paths (openai v3)."""

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest
from loguru import logger

from music_minion.domain.ai import client as ai_client
from music_minion.domain.ai.client import AIError, get_openai_client
from music_minion.domain.playlists import ai_parser


def _auth_error() -> openai.AuthenticationError:
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx2.Response(401, request=request)
    return openai.AuthenticationError("Incorrect API key", response=response, body=None)


def _fake_client(create: Any) -> SimpleNamespace:
    return SimpleNamespace(responses=SimpleNamespace(create=create))


@pytest.fixture
def log_records() -> Iterator[list[Any]]:
    records: list[Any] = []
    sink_id = logger.add(lambda msg: records.append(msg.record), level="ERROR")
    yield records
    logger.remove(sink_id)


def test_get_openai_client_without_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_client, "get_api_key", lambda: None)
    with pytest.raises(AIError, match="No OpenAI API key"):
        get_openai_client()


def test_get_openai_client_builds_sync_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_client, "get_api_key", lambda: "sk-test")
    client = get_openai_client()
    assert isinstance(client, openai.OpenAI)
    assert client.api_key == "sk-test"


def test_parser_api_error_logs_exception(
    monkeypatch: pytest.MonkeyPatch, log_records: list[Any]
) -> None:
    def create(**_: Any) -> None:
        raise _auth_error()

    monkeypatch.setattr(ai_parser, "get_openai_client", lambda: _fake_client(create))
    with pytest.raises(AIError, match="OpenAI API error"):
        ai_parser.parse_natural_language_to_filters("all dubstep")
    assert log_records, "expected logger.exception to fire"
    assert log_records[0]["exception"] is not None


def test_parser_keeps_validation_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    response = SimpleNamespace(output_text="not json", usage=None)
    monkeypatch.setattr(
        ai_parser, "get_openai_client", lambda: _fake_client(lambda **_: response)
    )
    with pytest.raises(AIError, match="^AI returned invalid JSON"):
        ai_parser.parse_natural_language_to_filters("all dubstep")
