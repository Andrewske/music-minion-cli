from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from web.backend.preference_model import (
    TrackFeatures,
    TrainingExample,
    artifact_from_json,
    artifact_to_json,
    chronological_split,
    evaluate_model,
    explanation,
    fit_model,
    normalize_genre,
    score_features,
)
from web.backend.preference_scoring import (
    ScoredCandidate,
    aggregate_artist_role_stats,
    bayesian_keep_rate,
    load_active_model,
    promote_model,
    score_feed_items,
    select_with_exploration,
    shadow_ordering_metrics,
    should_retrain,
    store_model,
)


def _examples(count: int = 50) -> list[TrainingExample]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    output = []
    for index in range(count):
        positive = index % 4 == 0 or index % 11 == 0
        features = TrackFeatures(
            duration_ms=180_000 if positive else 420_000,
            followed_uploader=positive,
            uploader_rank=20 if positive else None,
            reposter_count=3 if positive else 1,
            best_reposter_rank=40 if positive else 300,
            uploader_keep_rate=0.4 if positive else None,
            uploader_rated_count=float(index),
            reposter_keep_rate=0.3 if positive else 0.1,
            reposter_rated_count=float(index // 2),
            event_type="both" if positive else "repost",
            genre="Drum and Bass" if positive else "ambient",
            title="Short Edit" if positive else "Long Mix",
            release_age_days=float(index),
            repost_lag_days=2.0,
            as_of=(start + timedelta(days=index)).isoformat(),
        )
        output.append(
            TrainingExample(
                soundcloud_id=str(index),
                decided_at=(start + timedelta(days=index)).isoformat(),
                label=int(positive),
                features=features,
            )
        )
    return output


def test_chronological_split_never_shuffles_future_into_train() -> None:
    split = chronological_split(list(reversed(_examples(10))))
    assert split.train[-1].decided_at < split.validation[0].decided_at
    assert split.validation[-1].decided_at < split.test[0].decided_at


def test_model_is_deterministic_portable_and_bounded() -> None:
    examples = _examples()
    first = fit_model(examples, "test-v1")
    second = fit_model(examples, "test-v1")
    assert first.coefficients == pytest.approx(second.coefficients)
    restored = artifact_from_json(artifact_to_json(first))
    probability = score_features(restored, examples[0].features)
    assert 0 < probability < 1
    assert probability == pytest.approx(score_features(first, examples[0].features))


def test_evaluation_includes_baselines_ablations_calibration_and_ship_gate() -> None:
    _, report = evaluate_model(_examples(60), "evaluation", bootstrap_iterations=20)
    assert set(report["comparisons"]) == {
        "logistic_regression",
        "prior",
        "current_builder",
        "combined_heuristic",
    }
    assert "reposters" in report["feature_ablations"]
    assert (
        report["cold_start"]["artist_ids"] == "raw artist IDs are never model features"
    )
    assert report["recommendation"] in {"ship-shadow-only", "do-not-ship"}


def test_genre_normalization_and_concise_explanation() -> None:
    assert normalize_genre(" Drum_and_Bass ") == "drum & bass"
    text = explanation(
        TrackFeatures(
            followed_uploader=True,
            reposter_count=3,
            best_reposter_rank=42,
            duration_ms=198_000,
        )
    )
    assert text == "followed uploader · 3 reposters · best rank #42 · 3:18"


def test_role_stats_separate_uploads_and_fractionally_attribute_reposts() -> None:
    decisions = [
        {
            "soundcloud_id": "one",
            "decision": "keep",
            "decided_at": "2026-01-01",
            "uploader_id": 1,
            "reposter_ids": [2, 3],
        },
        {
            "soundcloud_id": "two",
            "decision": "nope",
            "decided_at": "2026-01-02",
            "uploader_id": 1,
            "reposter_ids": [2],
        },
        # A duplicate current-state row must not create a second example.
        {
            "soundcloud_id": "two",
            "decision": "keep",
            "decided_at": "2026-01-03",
            "uploader_id": 1,
            "reposter_ids": [2],
        },
    ]
    stats = {
        (row.artist_id, row.role): row for row in aggregate_artist_role_stats(decisions)
    }
    assert stats[(1, "upload")].rated_weight == 2
    assert stats[(1, "upload")].kept_weight == 1
    assert stats[(2, "repost")].rated_weight == 1.5
    assert stats[(2, "repost")].kept_weight == 0.5
    assert stats[(3, "repost")].rated_weight == 0.5
    assert stats[(3, "repost")].kept_weight == 0.5


def test_bayesian_rate_uses_prior_for_cold_start() -> None:
    assert bayesian_keep_rate(0, 0) == pytest.approx(0.22)
    assert bayesian_keep_rate(1, 1) < 1


def test_exploration_is_deterministic_unique_and_diverse() -> None:
    candidates = [
        ScoredCandidate(
            soundcloud_id=str(index),
            probability=1 - index / 20,
            uploader_id=index // 3,
            reposter_ids=(index // 2,),
            payload={},
        )
        for index in range(20)
    ]
    first = select_with_exploration(
        candidates, 10, exploration_share=0.2, per_uploader_cap=2, seed=7
    )
    second = select_with_exploration(
        candidates, 10, exploration_share=0.2, per_uploader_cap=2, seed=7
    )
    assert [row.soundcloud_id for row in first] == [row.soundcloud_id for row in second]
    assert len({row.soundcloud_id for row in first}) == len(first)
    assert any(row.probability <= 0.5 for row in first)


def test_retraining_is_thresholded_and_at_most_daily() -> None:
    now = datetime(2026, 9, 12, 20, tzinfo=timezone.utc)
    assert not should_retrain(24, None, now=now)
    assert should_retrain(25, None, now=now)
    assert not should_retrain(25, now.isoformat(), now=now)
    assert should_retrain(25, (now - timedelta(days=1)).isoformat(), now=now)


def test_shadow_ordering_reports_overlap_without_changing_builder() -> None:
    builder = ["a", "b", "c", "d"]
    model = ["b", "a", "e", "f"]
    metrics = shadow_ordering_metrics(builder, model, limit=4)
    assert builder == ["a", "b", "c", "d"]
    assert metrics["top_overlap"] == pytest.approx(0.5)
    assert metrics["mean_rank_shift"] > 0


def test_unknown_features_have_stable_cold_start_score() -> None:
    artifact = fit_model(_examples(), "cold-start")
    unknown = TrackFeatures()
    assert score_features(artifact, unknown) == pytest.approx(
        score_features(artifact, replace(unknown)), rel=0, abs=0
    )


def _model_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE preference_models (
            version TEXT PRIMARY KEY,
            feature_schema_version TEXT,
            status TEXT,
            trained_at TEXT,
            promoted_at TEXT,
            training_start TEXT,
            training_end TEXT,
            sample_count INTEGER,
            positive_count INTEGER,
            validation_metrics TEXT,
            coefficients TEXT,
            artifact_identity TEXT,
            ship_gate_passed INTEGER DEFAULT 0
        );
        CREATE TABLE preference_scores (
            soundcloud_id TEXT,
            model_version TEXT,
            keep_probability REAL,
            scored_at TEXT,
            feature_snapshot TEXT,
            explanation TEXT,
            PRIMARY KEY (soundcloud_id, model_version)
        );
        """
    )
    return conn


def test_promotion_requires_positive_ship_gate_and_replaces_active_model() -> None:
    conn = _model_conn()
    blocked = fit_model(_examples(), "blocked")
    approved = fit_model(_examples(), "approved")
    store_model(conn, blocked)
    store_model(conn, approved, ship_gate_passed=True)
    with pytest.raises(ValueError, match="ship gate"):
        promote_model(conn, "blocked")
    promote_model(conn, "approved")
    assert load_active_model(conn).version == "approved"


def test_score_feed_items_persists_versioned_score_and_explanation() -> None:
    conn = _model_conn()
    artifact = fit_model(_examples(), "active")
    store_model(conn, artifact, ship_gate_passed=True)
    promote_model(conn, "active")
    items = [
        {
            "soundcloud_id": "123",
            "title": "Track",
            "duration_ms": 198_000,
            "source": "release",
            "uploaded_at": "2026-01-01T00:00:00+00:00",
            "uploader": {"is_following": True, "ranking": 42},
            "reposters": [],
        }
    ]
    scored = score_feed_items(conn, items, scored_at="2026-02-01T00:00:00+00:00")
    assert 0 < scored[0]["keep_probability"] < 1
    assert scored[0]["prediction_model_version"] == "active"
    row = conn.execute("SELECT * FROM preference_scores").fetchone()
    assert row["soundcloud_id"] == "123"
    assert row["model_version"] == "active"
