"""Pure model primitives: features, splits, fitting, metrics, evaluation shape."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from web.backend.preference_model import (
    ABLATION_GROUPS,
    TrackFeatures,
    TrainingExample,
    artifact_from_json,
    artifact_to_json,
    bootstrap_confidence_intervals,
    builder_probabilities,
    calibration_bins,
    chronological_split,
    combined_heuristic_probabilities,
    evaluate_model,
    evaluate_probabilities,
    feature_dict,
    fit_model,
    normalize_genre,
    paired_bootstrap_delta,
    score_features,
    select_regularization,
    ship_gate,
    without_features,
)


def _examples(count: int = 60, group_size: int = 1) -> list[TrainingExample]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    output = []
    for index in range(count):
        positive = index % 4 == 0 or index % 11 == 0
        features = TrackFeatures(
            duration_ms=180_000 if positive else 420_000,
            followed_uploader=positive,
            uploader_rank=20 if positive else None,
            reposter_count=3 if positive else 1,
            top200_reposter_count=2 if positive else 0,
            best_reposter_rank=40 if positive else 300,
            uploader_keep_rate=0.4 if positive else None,
            uploader_rated_count=float(index),
            reposter_keep_rate=0.3 if positive else 0.1,
            reposter_rated_count=float(index // 2),
            best_reposter_keep_rate=0.3 if positive else 0.1,
            best_reposter_legacy_hit_rate=0.5 if positive else 0.0,
            event_type="both" if positive else "repost",
            genre="Drum and Bass" if positive else "ambient",
            title="Short Edit" if positive else "Long Mix",
            release_age_days=float(index),
            repost_lag_days=2.0,
        )
        decided = start + timedelta(days=index // group_size)
        output.append(
            TrainingExample(
                soundcloud_id=f"{index:03d}",
                decided_at=decided.isoformat(),
                label=int(positive),
                features=features,
                decided_at_source="test",
            )
        )
    return output


def test_split_is_chronological_and_keeps_decision_groups_whole() -> None:
    split = chronological_split(list(reversed(_examples(50, group_size=7))))
    assert split.train[-1].decided_at < split.validation[0].decided_at
    assert split.validation[-1].decided_at < split.test[0].decided_at
    assert len(split.train) + len(split.validation) + len(split.test) == 50
    with pytest.raises(ValueError):
        chronological_split(_examples(4))


def test_feature_dict_bands_and_missing_indicators() -> None:
    row = feature_dict(TrackFeatures(), ())
    assert row["duration_missing"] == 1 and row["uploader_rank_missing"] == 1
    assert row["best_reposter_rank_le_200"] == 0
    assert row["uploader_rate_missing"] == 1 and row["uploader_keep_rate"] == 0.22
    assert row["genre=other"] == 1
    known = feature_dict(
        TrackFeatures(
            duration_ms=300_000,
            best_reposter_rank=60,
            top200_reposter_count=3,
            title="Big Room Mix",
            genre="DnB",
        ),
        ("drum & bass",),
    )
    assert known["duration_over_4m"] == 1 and known["duration_over_7m"] == 0
    assert (
        known["best_reposter_rank_le_75"] == 1
        and known["best_reposter_rank_le_25"] == 0
    )
    assert known["multi_top200_reposters"] == 1
    assert known["title_mix"] == 1
    assert known["genre=drum & bass"] == 1 and known["genre=other"] == 0
    assert normalize_genre(" Drum_and_Bass ") == "drum & bass"


def test_model_is_deterministic_portable_and_bounded() -> None:
    examples = _examples()
    first = fit_model(examples, "test-v1")
    second = fit_model(examples, "test-v1")
    assert first.coefficients == pytest.approx(second.coefficients)
    restored = artifact_from_json(artifact_to_json(first))
    probability = score_features(restored, examples[0].features)
    assert 0 < probability < 1
    assert probability == pytest.approx(score_features(first, examples[0].features))
    assert not any(name.startswith("artist") for name in first.feature_names)


def test_model_separates_the_synthetic_classes() -> None:
    examples = _examples(80)
    artifact = fit_model(examples[:60], "sep", regularization_c=1.0)
    positives = [score_features(artifact, e.features) for e in examples[60:] if e.label]
    negatives = [
        score_features(artifact, e.features) for e in examples[60:] if not e.label
    ]
    assert min(positives) > max(negatives)


def test_regularization_is_selected_on_validation_log_loss() -> None:
    examples = _examples(80)
    c, table = select_regularization(examples[:50], examples[50:], (), grid=(0.01, 1.0))
    assert c in {0.01, 1.0}
    assert [row["c"] for row in table] == [0.01, 1.0]
    assert c == min(table, key=lambda row: row["log_loss"])["c"]


def test_metrics_and_calibration_shape() -> None:
    labels = [1, 0, 1, 0, 0, 0, 1, 0, 0, 0]
    probabilities = [0.9, 0.1, 0.8, 0.2, 0.3, 0.1, 0.7, 0.4, 0.2, 0.1]
    metrics = evaluate_probabilities(labels, probabilities)
    assert metrics["precision_at_20"] == pytest.approx(0.3)
    assert metrics["bottom_decile_keep_rate"] == 0
    assert metrics["auc"] == 1.0
    assert metrics["brier_score"] < 0.1
    bins = calibration_bins(labels, probabilities, bins=5)
    assert sum(item["count"] for item in bins) == 10
    intervals = bootstrap_confidence_intervals(labels, probabilities, iterations=50)
    assert (
        intervals["brier_score"][0]
        <= metrics["brier_score"]
        <= intervals["brier_score"][1]
    )
    delta = paired_bootstrap_delta(
        labels, probabilities, [0.3] * 10, "brier_score", iterations=50
    )
    assert delta["point"] > 0 and delta["low"] <= delta["point"] <= delta["high"]


def test_baselines_use_only_decision_time_fields() -> None:
    examples = _examples(8)
    assert builder_probabilities(examples)[0] == pytest.approx(0.3)
    assert builder_probabilities(examples)[1] == pytest.approx(0.1)
    heuristic = combined_heuristic_probabilities(examples)
    assert heuristic[0] > heuristic[1]
    assert all(0.01 <= p <= 0.95 for p in heuristic)


def test_ablation_resets_only_the_named_fields() -> None:
    examples = _examples(4)
    stripped = without_features(examples, ABLATION_GROUPS["rank_signals"])
    assert stripped[0].features.best_reposter_rank is None
    assert stripped[0].features.top200_reposter_count == 0
    assert stripped[0].features.followed_uploader is True
    assert examples[0].features.best_reposter_rank == 40


def test_ship_gate_lists_every_failed_check() -> None:
    good = {"precision_at_50": 0.4, "bottom_decile_keep_rate": 0.05}
    prior = {"base_keep_rate": 0.22, "precision_at_50": 0.22}
    builder = {"precision_at_50": 0.25}
    passed, failed = ship_gate(good, prior, builder, {"low": 0.01}, {"low": 0.01})
    assert passed and failed == []
    passed, failed = ship_gate(
        {"precision_at_50": 0.2, "bottom_decile_keep_rate": 0.3},
        prior,
        builder,
        {"low": -0.01},
        {"low": 0.01},
    )
    assert not passed
    assert failed == [
        "brier beats prior with CI above zero",
        "precision@50 beats current builder",
        "bottom decile below base rate",
    ]


def test_evaluation_report_has_baselines_ablations_calibration_and_verdict() -> None:
    artifact, report = evaluate_model(
        _examples(120, group_size=3), "evaluation", bootstrap_iterations=20
    )
    assert set(report["comparisons"]) == {
        "logistic_regression",
        "prior",
        "current_builder",
        "legacy_builder",
        "combined_heuristic",
    }
    assert set(report["feature_ablations"]) == set(ABLATION_GROUPS)
    assert "brier_score_vs_prior" in report["paired_deltas"]
    assert (
        report["split"]["train"]
        + report["split"]["validation"]
        + report["split"]["test"]
        == 120
    )
    assert report["regularization"]["selected_c"] == artifact.regularization_c
    assert report["decided_at_sources"] == {"test": 120}
    assert report["recommendation"] in {"ship-shadow", "no-ship"}
    assert report["coefficients"][0]["feature"] in artifact.feature_names


def test_unknown_features_score_at_a_stable_cold_start_value() -> None:
    artifact = fit_model(_examples(), "cold-start")
    unknown = score_features(artifact, TrackFeatures())
    assert unknown == score_features(artifact, TrackFeatures(title=""))
    assert 0 <= unknown <= 1
