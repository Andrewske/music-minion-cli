"""Feed agent (#31): Jev mix classifier, rule-suggestion mining, endpoints.

Jev is always mocked: no test reaches OpenRouter.
"""

import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from music_minion.core.database import get_db_connection
from tests.test_feed_uploads import _insert_artist, _insert_upload, test_db  # noqa: F401
from web.backend import jev_client
from web.backend.feed_classifier import (
    batch_results,
    build_questions,
    build_state,
    classification_status,
    is_ambiguous,
)
from web.backend.jev_client import JevConfig
from web.backend.queries import feed_filters as filter_queries
from web.backend.rule_suggestions import keyword_regex, mine_suggestions

MIN = 60_000


def _flag(title: str, minutes: float = 3, reason: str = "podcast", **extra) -> dict:
    return {
        "title": title,
        "duration_ms": int(minutes * MIN),
        "reason": reason,
        **extra,
    }


def _reviewed(title: str, decision: str = "keep", minutes: float = 3) -> dict:
    return {"title": title, "decision": decision, "duration_ms": int(minutes * MIN)}


# ---------------------------------------------------------------------------
# Suggestion mining (pure)
# ---------------------------------------------------------------------------


class TestMining:
    def test_repeated_phrase_becomes_a_suggestion(self) -> None:
        flags = [_flag(f"Radio Show {n}") for n in range(4)] + [_flag("Other")]
        (suggestion,) = mine_suggestions(flags, [], [], [])
        assert suggestion["kind"] == "title_regex"
        assert suggestion["name"] == 'Title has "radio show"'
        assert suggestion["support"] == 4 and suggestion["counter"] == 0
        assert suggestion["reason"] == "podcast"
        assert suggestion["evidence"].startswith("4 of your 5 flags")

    def test_below_min_support_is_ignored(self) -> None:
        assert (
            mine_suggestions([_flag("Radio Show 1"), _flag("Radio Show 2")], [], [], [])
            == []
        )

    def test_real_tracks_lower_precision(self) -> None:
        flags = [_flag(f"Weekly Session {n}") for n in range(4)]
        reviewed = [_reviewed("Session Vibes"), _reviewed("Studio Session")]
        names = {s["name"] for s in mine_suggestions(flags, [], reviewed, [])}
        assert 'Title has "session"' not in names  # 4 / 6 < 0.8
        assert 'Title has "weekly session"' in names

    def test_rescues_count_against_but_nopes_do_not(self) -> None:
        flags = [_flag(f"Guest Hour {n}") for n in range(4)]
        nopes = [_reviewed(f"Guest Hour {n}", "nope") for n in range(5)]
        assert mine_suggestions(flags, [], nopes, [])
        rescued = [_flag("Guest Hour Tune")] * 2
        assert not mine_suggestions(flags, rescued, nopes, [])

    def test_flags_already_caught_by_a_rule_do_not_count(self) -> None:
        flags = [_flag(f"Radio Show {n}") for n in range(4)]
        rule = {"id": 1, "kind": "title_regex", "pattern": "radio", "enabled": True}
        assert mine_suggestions(flags, [], [], [rule]) == []
        assert mine_suggestions(flags, [], [], [{**rule, "enabled": False}])

    def test_loosest_qualifying_duration(self) -> None:
        flags = [
            _flag(f"Track {n}", minutes=11 + n, reason="live_mix") for n in range(3)
        ]
        reviewed = [_reviewed("Long Keep", "not_quite", minutes=9)]
        durations = [
            s
            for s in mine_suggestions(flags, [], reviewed, [])
            if s["kind"] == "duration_min"
        ]
        assert [(s["threshold"], s["reason"]) for s in durations] == [
            (10.0, "live_mix")
        ]

    def test_tags_suggest_tag_rules(self) -> None:
        flags = [_flag(f"Ep {n}", genre="Talk", tags=["talk show"]) for n in range(3)]
        patterns = {
            s["pattern"]
            for s in mine_suggestions(flags, [], [], [])
            if s["kind"] == "tag_match"
        }
        assert patterns == {"talk", "talk show"}

    def test_variant_keyword_regexes_pass_rule_validation(self) -> None:
        from web.backend.feed_filter_rules import validate_rule
        from web.backend.rule_suggestions import _VARIANT_REGEX

        for keyword in [*_VARIANT_REGEX, "radio show", "guest mix 12"]:
            validate_rule(
                {"name": "x", "kind": "title_regex", "pattern": keyword_regex(keyword), "reason": "other"}
            )

    def test_unacceptable_candidates_are_never_suggested(self, monkeypatch) -> None:
        from web.backend import rule_suggestions

        monkeypatch.setattr(rule_suggestions, "keyword_regex", lambda _kw: "(a+)+$")
        flags = [_flag(f"Radio Show {n}") for n in range(4)]
        assert mine_suggestions(flags, [], [], []) == []

    def test_variant_keyword_regex_matches_every_spelling(self) -> None:
        import re

        pattern = keyword_regex("acapella")
        for title in ("A Cappella", "acapella", "Accapella"):
            assert re.search(pattern, title, re.IGNORECASE)
        assert re.search(keyword_regex("radio show"), "Radio - Show", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Classifier (pure)
# ---------------------------------------------------------------------------


class TestClassifierPure:
    @pytest.mark.parametrize(
        ("probability", "status"),
        [
            (0.9, "auto_flagged"),
            (0.85, "auto_flagged"),
            (0.84, "pending"),
            (0.5, "pending"),
            (0.49, "below_threshold"),
        ],
    )
    def test_thresholds(self, probability: float, status: str) -> None:
        assert classification_status(probability) == status

    def test_ambiguous_is_8_to_20_min_without_rule_hit(self) -> None:
        rule = {"id": 1, "kind": "title_regex", "pattern": "live at", "enabled": True}
        assert is_ambiguous({"title": "Tune", "duration_ms": 9 * MIN}, [rule])
        assert not is_ambiguous({"title": "Tune", "duration_ms": 5 * MIN}, [rule])
        assert not is_ambiguous({"title": "Tune", "duration_ms": 25 * MIN}, [rule])
        assert not is_ambiguous({"title": "Live at X", "duration_ms": 9 * MIN}, [rule])

    def test_state_and_questions(self) -> None:
        batch = [{"title": "A", "duration_ms": 9 * MIN}, {"title": "B"}]
        state = json.loads(build_state(batch, [{"title": "Mix"}], [{"title": "Song"}]))
        assert set(state["tracks"]) == {"t0", "t1"}
        assert [e["is_mix_or_show"] for e in state["examples"]] == [True, False]
        assert state["tracks"]["t0"]["duration_min"] == 9.0
        assert len(build_questions(2)) == 4

    def test_batch_results_skip_unanswered(self) -> None:
        batch = [{"soundcloud_id": "1"}, {"soundcloud_id": "2"}]
        (result,) = batch_results(batch, {"mix_t0": 0.9, "podcast_t0": 0.8})
        assert result["status"] == "auto_flagged" and result["reason"] == "podcast"


# ---------------------------------------------------------------------------
# DB + API
# ---------------------------------------------------------------------------


@pytest.fixture
def client(test_db):  # noqa: F811
    from web.backend.routers.feed_agent import router as agent_router
    from web.backend.routers.feed_filters import router as filters_router
    from web.backend.routers.insights import router as insights_router

    app = FastAPI()
    app.include_router(filters_router)
    app.include_router(agent_router)
    app.include_router(insights_router)
    return TestClient(app)


def _seed(tracks: dict[str, tuple[str, float]]) -> None:
    """sc_id -> (title, minutes) as unreviewed uploads."""
    with get_db_connection() as conn:
        artist_id = _insert_artist(conn)
        for sc_id, (title, minutes) in tracks.items():
            _insert_upload(
                conn, artist_id, sc_id, "2026-07-01T00:00:00+00:00", title=title
            )
            conn.execute(
                "UPDATE sc_artist_uploads SET duration_ms = ? WHERE soundcloud_id = ?",
                (int(minutes * MIN), sc_id),
            )
        conn.commit()


@pytest.fixture
def jev(monkeypatch):
    """Fake Jev: P(mix) per title from `answers`; records every call."""
    calls: list[dict] = []
    answers: dict[str, float] = {}

    def fake_ask(config, state, questions, timeout_s=30.0):
        tracks = json.loads(state)["tracks"]
        calls.append({"tracks": tracks, "questions": questions})
        return {
            f"mix_{key}": answers.get(track["title"], 0.1)
            for key, track in tracks.items()
        }

    monkeypatch.setattr(
        jev_client, "get_jev_config", lambda: JevConfig("https://x", "k", "jev-test")
    )
    monkeypatch.setattr(jev_client, "ask_nouls", fake_ask)
    return calls, answers


def _flags() -> dict[str, dict]:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM sc_track_flags").fetchall()
    return {row["soundcloud_id"]: dict(row) for row in rows}


class TestClassifyRun:
    def test_batches_thresholds_and_no_rerun(self, client, jev) -> None:
        calls, answers = jev
        tracks = {str(100 + n): (f"Track {n}", 10) for n in range(12)}
        tracks |= {"200": ("Short", 3), "201": ("Live at Fest", 10)}
        _seed(tracks)
        answers |= {"Track 0": 0.95, "Track 1": 0.6}

        summary = client.post("/api/feed-filters/classify").json()

        assert [len(call["tracks"]) for call in calls] == [10, 2]
        assert summary == {
            "candidates": 12,
            "classified": 12,
            "auto_flagged": 1,
            "pending": 1,
            "failed_batches": 0,
        }
        flag = _flags()["100"]
        assert (flag["source"], flag["confidence"], flag["reason"]) == (
            "agent",
            0.95,
            "live_mix",
        )
        assert set(_flags()) == {"100"}
        pending = client.get("/api/feed-filters/classifications").json()["items"]
        assert [item["soundcloud_id"] for item in pending] == ["101"]
        assert client.post("/api/feed-filters/classify").json()["candidates"] == 0

    def test_agent_never_flags_a_track_rated_or_rescued_mid_run(
        self, client, jev, monkeypatch
    ) -> None:
        from web.backend.queries import feed as feed_queries

        _, answers = jev
        _seed({"100": ("Track A", 10), "101": ("Track B", 10)})
        answers |= {"Track A": 0.95, "Track B": 0.95}
        real_ask = jev_client.ask_nouls

        # While Jev runs, Kevin nopes 100 and a rule flag on 101 is rescued.
        def rate_and_rescue_first(config, state, questions, timeout_s=30.0):
            feed_queries.record_decision("100", "nope", "test")
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO sc_track_flags (soundcloud_id, reason, source, rescued_at) "
                    "VALUES ('101', 'other', 'rule', CURRENT_TIMESTAMP)"
                )
                conn.commit()
            return real_ask(config, state, questions, timeout_s)

        monkeypatch.setattr(jev_client, "ask_nouls", rate_and_rescue_first)
        client.post("/api/feed-filters/classify")
        assert {sc_id: flag["source"] for sc_id, flag in _flags().items()} == {"101": "rule"}

    def test_failed_batch_is_counted(self, client, jev, monkeypatch) -> None:
        _seed({"100": ("Track", 10)})

        def boom(*_args, **_kwargs):
            raise httpx.ConnectError("down")

        monkeypatch.setattr(jev_client, "ask_nouls", boom)
        summary = client.post("/api/feed-filters/classify").json()
        assert summary["failed_batches"] == 1 and summary["classified"] == 0

    def test_unconfigured_is_503(self, client, monkeypatch) -> None:
        monkeypatch.setattr(jev_client, "get_jev_config", lambda: None)
        assert client.post("/api/feed-filters/classify").status_code == 503

    def test_confirm_flags_and_dismiss_becomes_negative(
        self, client, jev, monkeypatch
    ) -> None:
        _, answers = jev
        refreshed: list[list[str]] = []
        monkeypatch.setattr(
            filter_queries, "refresh_artist_stats_for", lambda ids: refreshed.append(list(ids))
        )
        _seed({"100": ("Maybe Show", 10), "101": ("Maybe Song", 10)})
        answers |= {"Maybe Show": 0.7, "Maybe Song": 0.6}
        client.post("/api/feed-filters/classify")
        items = client.get("/api/feed-filters/classifications").json()["items"]
        by_id = {item["soundcloud_id"]: item["id"] for item in items}

        confirmed = client.post(
            f"/api/feed-filters/classifications/{by_id['100']}/confirm"
        )
        assert confirmed.json()["status"] == "confirmed"
        assert _flags()["100"]["source"] == "user"
        assert refreshed == [["100"]]
        client.post(f"/api/feed-filters/classifications/{by_id['101']}/dismiss")
        assert "101" not in _flags()
        again = client.post(f"/api/feed-filters/classifications/{by_id['101']}/confirm")
        assert again.status_code == 409

        from web.backend.queries.feed_agent import load_not_mix_examples

        assert [t["soundcloud_id"] for t in load_not_mix_examples()] == ["101"]

    def test_agent_flags_sort_lowest_confidence_first(self, client, jev) -> None:
        _, answers = jev
        _seed({"100": ("A", 10), "101": ("B", 10), "102": ("Podcast thing", 30)})
        answers |= {"A": 0.99, "B": 0.86}
        client.post("/api/feed-filters/classify")
        filter_queries.apply_rules(None)  # seed rules flag the 30-minute one
        page = client.get(
            "/api/feed-filters/tracks", params={"sort": "confidence", "limit": 2}
        ).json()
        assert [i["soundcloud_id"] for i in page["items"]] == ["101", "100"]
        assert page["next_cursor_confidence"] == 0.99
        rest = client.get(
            "/api/feed-filters/tracks",
            params={
                "sort": "confidence",
                "cursor": page["next_cursor"],
                "cursor_confidence": page["next_cursor_confidence"],
            },
        ).json()
        assert [i["soundcloud_id"] for i in rest["items"]] == ["102"]


class TestSuggestionsApi:
    def _flag_titles(self, client, titles: list[str]) -> None:
        _seed({str(300 + n): (title, 3) for n, title in enumerate(titles)})
        for n in range(len(titles)):
            filter_queries.flag_track(str(300 + n), "podcast")

    def test_mine_accept_creates_a_real_rule(self, client) -> None:
        self._flag_titles(client, [f"Guest Hour {n}" for n in range(3)])
        mined = client.post("/api/feed-filters/suggestions/mine").json()
        suggestion = next(
            s for s in mined["suggestions"] if s["name"] == 'Title has "guest hour"'
        )
        accepted = client.post(
            f"/api/feed-filters/suggestions/{suggestion['id']}/accept"
        )
        assert accepted.status_code == 201, accepted.text
        rule = accepted.json()["rule"]
        assert (rule["kind"], rule["reason"]) == ("title_regex", "podcast")
        assert accepted.json()["suggestion"]["rule_id"] == rule["id"]
        again = client.post(f"/api/feed-filters/suggestions/{suggestion['id']}/accept")
        assert again.status_code == 409

    def test_invalid_regex_override_is_422(self, client) -> None:
        self._flag_titles(client, [f"Guest Hour {n}" for n in range(3)])
        suggestion = client.post("/api/feed-filters/suggestions/mine").json()[
            "suggestions"
        ][0]
        response = client.post(
            f"/api/feed-filters/suggestions/{suggestion['id']}/accept",
            json={"pattern": "(unclosed"},
        )
        assert response.status_code == 422
        assert "Invalid regex" in response.json()["detail"]

    def test_dismissed_suggestion_never_returns(self, client) -> None:
        self._flag_titles(client, [f"Guest Hour {n}" for n in range(3)])
        suggestions = client.post("/api/feed-filters/suggestions/mine").json()[
            "suggestions"
        ]
        for suggestion in suggestions:
            client.post(f"/api/feed-filters/suggestions/{suggestion['id']}/dismiss")
        assert (
            client.post("/api/feed-filters/suggestions/mine").json()["suggestions"]
            == []
        )
        dismissed = client.get(
            "/api/feed-filters/suggestions", params={"status": "dismissed"}
        )
        assert len(dismissed.json()["suggestions"]) == len(suggestions)

    def test_stale_pending_suggestions_are_dropped(self, client) -> None:
        self._flag_titles(client, [f"Guest Hour {n}" for n in range(3)])
        assert client.post("/api/feed-filters/suggestions/mine").json()["suggestions"]
        for n in range(3):
            filter_queries.unflag_track(str(300 + n))
        assert (
            client.post("/api/feed-filters/suggestions/mine").json()["suggestions"]
            == []
        )

    def test_unknown_suggestion_is_404(self, client) -> None:
        assert (
            client.post("/api/feed-filters/suggestions/999/dismiss").status_code == 404
        )


class TestInsightsApi:
    def test_rejects_unknown_dimension(self, client) -> None:
        assert (
            client.get("/api/insights", params={"dimension": "description"}).status_code
            == 422
        )

    def test_empty_db(self, client) -> None:
        body = client.get("/api/insights").json()
        assert body["overall"] == {"seen": 0, "keep_pct": 0.0}
        assert body["rows"] == [] and body["min_count"] == 8
