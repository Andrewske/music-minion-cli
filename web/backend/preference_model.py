"""Pure keep-probability model primitives: features, fitting, evaluation.

No database access lives here. The dataset builder
(:mod:`keep_model_dataset`) produces :class:`TrainingExample` rows and the
evaluation script renders the report. Nothing in production selection calls
this module (ticket #61 is evaluation only).
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

FEATURE_SCHEMA_VERSION = "keep-v2"
DEFAULT_PRIOR = 0.22
UNKNOWN_GENRE = "other"
REGULARIZATION_GRID: tuple[float, ...] = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0)
TOP200 = 200


@dataclass(frozen=True)
class TrackFeatures:
    """What was known about a track when it was surfaced.

    Rates must be computed only from decisions strictly before this one.
    ``best_reposter_*`` fields feed the builder baselines, not the model.
    """

    duration_ms: int | None = None
    followed_uploader: bool = False
    uploader_rank: int | None = None
    reposter_count: int = 0
    top200_reposter_count: int = 0
    best_reposter_rank: int | None = None
    uploader_keep_rate: float | None = None
    uploader_rated_count: float = 0.0
    reposter_keep_rate: float | None = None
    reposter_rated_count: float = 0.0
    best_reposter_keep_rate: float | None = None
    best_reposter_legacy_hit_rate: float | None = None
    event_type: str = "repost"
    genre: str | None = None
    title: str = ""
    release_age_days: float | None = None
    repost_lag_days: float | None = None


@dataclass(frozen=True)
class TrainingExample:
    soundcloud_id: str
    decided_at: str
    label: int
    features: TrackFeatures
    decided_at_source: str = "unknown"


@dataclass(frozen=True)
class DatasetSplit:
    train: tuple[TrainingExample, ...]
    validation: tuple[TrainingExample, ...]
    test: tuple[TrainingExample, ...]


@dataclass(frozen=True)
class ModelArtifact:
    version: str
    feature_schema_version: str
    trained_at: str
    training_start: str
    training_end: str
    sample_count: int
    positive_count: int
    regularization_c: float
    feature_names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float
    common_genres: tuple[str, ...]
    validation_metrics: dict[str, float]


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------


def normalize_genre(value: str | None) -> str:
    """Collapse cosmetic genre variants into a stable, conservative token."""
    if not value:
        return UNKNOWN_GENRE
    normalized = " ".join(value.strip().lower().replace("_", " ").split())
    aliases = {
        "dnb": "drum & bass",
        "drum and bass": "drum & bass",
        "hiphop": "hip hop",
        "rnb": "r&b",
    }
    return aliases.get(normalized, normalized) or UNKNOWN_GENRE


def select_common_genres(
    examples: Sequence[TrainingExample], min_count: int = 10, max_genres: int = 20
) -> tuple[str, ...]:
    counts: dict[str, int] = {}
    for example in examples:
        genre = normalize_genre(example.features.genre)
        counts[genre] = counts.get(genre, 0) + 1
    ranked = sorted(
        ((count, genre) for genre, count in counts.items() if count >= min_count),
        key=lambda item: (-item[0], item[1]),
    )
    return tuple(genre for _, genre in ranked[:max_genres] if genre != UNKNOWN_GENRE)


def _rate_or_prior(rate: float | None) -> float:
    if rate is None or not math.isfinite(rate):
        return DEFAULT_PRIOR
    return min(1.0, max(0.0, rate))


def _rank_features(prefix: str, rank: int | None) -> dict[str, float]:
    """Log rank plus the bands from the prior analysis; unknown = worst band."""
    known = rank is not None
    value = float(rank) if known else 1_000.0
    return {
        f"{prefix}_missing": float(not known),
        f"{prefix}_log": math.log1p(value),
        f"{prefix}_le_25": float(known and value <= 25),
        f"{prefix}_le_75": float(known and value <= 75),
        f"{prefix}_le_200": float(known and value <= TOP200),
    }


def _duration_features(duration_ms: int | None) -> dict[str, float]:
    minutes = (duration_ms or 0) / 60_000
    return {
        "duration_minutes": minutes,
        "duration_missing": float(duration_ms is None),
        "duration_under_2m": float(duration_ms is not None and minutes < 2),
        "duration_over_4m": float(minutes > 4),
        "duration_over_7m": float(minutes > 7),
    }


def _title_features(title: str) -> dict[str, float]:
    text = title.lower()
    return {
        "title_mix": float(any(w in text for w in ("mix", "radio", "podcast", "set"))),
        "title_remix": float(
            any(w in text for w in ("remix", "refix", "edit", "flip", "bootleg"))
        ),
    }


def feature_dict(
    features: TrackFeatures, common_genres: Sequence[str]
) -> dict[str, float]:
    """Numeric feature mapping. Missing values get an indicator plus a neutral fill."""
    event_type = (
        features.event_type
        if features.event_type in {"release", "repost", "both"}
        else "repost"
    )
    genre = normalize_genre(features.genre)
    result: dict[str, float] = {
        **_duration_features(features.duration_ms),
        "followed_uploader": float(features.followed_uploader),
        **_rank_features("uploader_rank", features.uploader_rank),
        "reposter_count": float(max(0, features.reposter_count)),
        "log_reposter_count": math.log1p(max(0, features.reposter_count)),
        "top200_reposter_count": float(max(0, features.top200_reposter_count)),
        "multi_top200_reposters": float(features.top200_reposter_count >= 2),
        **_rank_features("best_reposter_rank", features.best_reposter_rank),
        "uploader_keep_rate": _rate_or_prior(features.uploader_keep_rate),
        "uploader_rate_missing": float(features.uploader_keep_rate is None),
        "log_uploader_samples": math.log1p(max(0.0, features.uploader_rated_count)),
        "reposter_keep_rate": _rate_or_prior(features.reposter_keep_rate),
        "reposter_rate_missing": float(features.reposter_keep_rate is None),
        "log_reposter_samples": math.log1p(max(0.0, features.reposter_rated_count)),
        "event_release": float(event_type in {"release", "both"}),
        "event_repost": float(event_type in {"repost", "both"}),
        **_title_features(features.title),
        "release_age_log_days": math.log1p(max(0.0, features.release_age_days or 0.0)),
        "release_age_missing": float(features.release_age_days is None),
        "repost_lag_log_days": math.log1p(max(0.0, features.repost_lag_days or 0.0)),
        "repost_lag_missing": float(features.repost_lag_days is None),
    }
    for known_genre in common_genres:
        result[f"genre={known_genre}"] = float(genre == known_genre)
    result[f"genre={UNKNOWN_GENRE}"] = float(genre not in common_genres)
    return result


# ---------------------------------------------------------------------------
# Splits and fitting
# ---------------------------------------------------------------------------


def _group_boundary(ordered: Sequence[TrainingExample], index: int) -> int:
    """Move a cut forward so examples decided at the same time stay together."""
    while (
        0 < index < len(ordered)
        and ordered[index].decided_at == ordered[index - 1].decided_at
    ):
        index += 1
    return index


def chronological_split(
    examples: Sequence[TrainingExample],
    train_fraction: float = 0.60,
    validation_fraction: float = 0.20,
) -> DatasetSplit:
    """Chronological split that never separates a decision group.

    Decision times are proxies with one-sync-cycle resolution, so a cut inside
    a group would put simultaneous decisions on both sides of the boundary.
    """
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1:
        raise ValueError("split fractions must be between zero and one")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("train + validation fraction must be below one")
    ordered = sorted(examples, key=lambda row: (row.decided_at, row.soundcloud_id))
    if len(ordered) < 5:
        raise ValueError("at least five definitive decisions are required")
    train_end = _group_boundary(ordered, int(len(ordered) * train_fraction))
    validation_end = _group_boundary(
        ordered, int(len(ordered) * (train_fraction + validation_fraction))
    )
    if not 0 < train_end < validation_end < len(ordered):
        raise ValueError("decision groups are too coarse for a three-way split")
    return DatasetSplit(
        train=tuple(ordered[:train_end]),
        validation=tuple(ordered[train_end:validation_end]),
        test=tuple(ordered[validation_end:]),
    )


def _matrix(
    examples: Sequence[TrainingExample],
    common_genres: Sequence[str],
    feature_names: Sequence[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    rows = [feature_dict(example.features, common_genres) for example in examples]
    names = tuple(feature_names or sorted(rows[0]))
    matrix = np.asarray(
        [[row.get(name, 0.0) for name in names] for row in rows], dtype=float
    )
    labels = np.asarray([example.label for example in examples], dtype=int)
    return matrix, labels, names


def fit_model(
    examples: Sequence[TrainingExample],
    version: str,
    regularization_c: float = 0.3,
    common_genres: Sequence[str] | None = None,
    validation_metrics: dict[str, float] | None = None,
) -> ModelArtifact:
    """Deterministic L2 logistic regression on standardized features."""
    if not examples:
        raise ValueError("cannot train without examples")
    if {example.label for example in examples} != {0, 1}:
        raise ValueError("training data must contain both keep and nope labels")
    genres = tuple(
        common_genres if common_genres is not None else select_common_genres(examples)
    )
    matrix, labels, names = _matrix(examples, genres)
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0)
    scales[scales == 0] = 1.0
    estimator = LogisticRegression(
        C=regularization_c, max_iter=5_000, random_state=0, solver="lbfgs"
    )
    estimator.fit((matrix - means) / scales, labels)
    ordered = sorted(examples, key=lambda row: (row.decided_at, row.soundcloud_id))
    return ModelArtifact(
        version=version,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        trained_at=datetime.now(timezone.utc).isoformat(),
        training_start=ordered[0].decided_at,
        training_end=ordered[-1].decided_at,
        sample_count=len(examples),
        positive_count=int(labels.sum()),
        regularization_c=regularization_c,
        feature_names=names,
        means=tuple(float(v) for v in means),
        scales=tuple(float(v) for v in scales),
        coefficients=tuple(float(v) for v in estimator.coef_[0]),
        intercept=float(estimator.intercept_[0]),
        common_genres=genres,
        validation_metrics=dict(validation_metrics or {}),
    )


def score_features(artifact: ModelArtifact, features: TrackFeatures) -> float:
    row = feature_dict(features, artifact.common_genres)
    values = np.asarray([row.get(name, 0.0) for name in artifact.feature_names])
    standardized = (values - np.asarray(artifact.means)) / np.asarray(artifact.scales)
    logit = artifact.intercept + float(
        np.dot(standardized, np.asarray(artifact.coefficients))
    )
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    exp_logit = math.exp(logit)
    return exp_logit / (1.0 + exp_logit)


def score_examples(
    artifact: ModelArtifact, examples: Sequence[TrainingExample]
) -> list[float]:
    return [score_features(artifact, example.features) for example in examples]


def select_regularization(
    train: Sequence[TrainingExample],
    validation: Sequence[TrainingExample],
    common_genres: Sequence[str],
    grid: Sequence[float] = REGULARIZATION_GRID,
) -> tuple[float, list[dict[str, float]]]:
    """Pick C by validation log loss (ties go to the stronger regularization)."""
    labels = [row.label for row in validation]
    table: list[dict[str, float]] = []
    for c in grid:
        artifact = fit_model(
            train, "grid", regularization_c=c, common_genres=common_genres
        )
        metrics = evaluate_probabilities(labels, score_examples(artifact, validation))
        table.append({"c": c, **metrics})
    best = min(table, key=lambda row: (round(row["log_loss"], 6), row["c"]))
    return float(best["c"]), table


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def evaluate_probabilities(
    labels: Sequence[int], probabilities: Sequence[float]
) -> dict[str, float]:
    if not labels or len(labels) != len(probabilities):
        raise ValueError("labels and probabilities must be non-empty and aligned")
    y = np.asarray(labels, dtype=int)
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    order = np.argsort(-p, kind="stable")
    bottom = max(1, math.ceil(len(y) / 10))
    result = {
        "sample_count": float(len(y)),
        "base_keep_rate": float(y.mean()),
        "brier_score": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "precision_at_20": float(y[order[: min(20, len(y))]].mean()),
        "precision_at_50": float(y[order[: min(50, len(y))]].mean()),
        "precision_at_100": float(y[order[: min(100, len(y))]].mean()),
        "bottom_decile_keep_rate": float(y[order[-bottom:]].mean()),
    }
    result["auc"] = float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else 0.5
    return result


def calibration_bins(
    labels: Sequence[int], probabilities: Sequence[float], bins: int = 10
) -> list[dict[str, float]]:
    y = np.asarray(labels, dtype=int)
    p = np.asarray(probabilities, dtype=float)
    output: list[dict[str, float]] = []
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        mask = (p >= low) & ((p <= high) if index == bins - 1 else (p < high))
        if not mask.any():
            continue
        output.append(
            {
                "low": low,
                "high": high,
                "count": float(mask.sum()),
                "mean_prediction": float(p[mask].mean()),
                "keep_rate": float(y[mask].mean()),
            }
        )
    return output


def expected_calibration_error(bins: Sequence[dict[str, float]]) -> float:
    total = sum(item["count"] for item in bins)
    if total == 0:
        return 0.0
    return (
        sum(
            abs(item["mean_prediction"] - item["keep_rate"]) * item["count"]
            for item in bins
        )
        / total
    )


def bootstrap_confidence_intervals(
    labels: Sequence[int],
    probabilities: Sequence[float],
    iterations: int = 1_000,
    seed: int = 0,
) -> dict[str, tuple[float, float]]:
    """Deterministic 95% bootstrap intervals for the evaluation metrics."""
    y = np.asarray(labels, dtype=int)
    p = np.asarray(probabilities, dtype=float)
    if len(y) < 2:
        return {}
    generator = np.random.default_rng(seed)
    samples: dict[str, list[float]] = {}
    for _ in range(iterations):
        idx = generator.integers(0, len(y), len(y))
        if y[idx].sum() in (0, len(idx)):
            continue
        metrics = evaluate_probabilities(y[idx].tolist(), p[idx].tolist())
        for name, value in metrics.items():
            if name != "sample_count":
                samples.setdefault(name, []).append(value)
    return {
        name: (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5)))
        for name, v in samples.items()
    }


def paired_bootstrap_delta(
    labels: Sequence[int],
    candidate: Sequence[float],
    baseline: Sequence[float],
    metric: str,
    iterations: int = 1_000,
    seed: int = 0,
) -> dict[str, float]:
    """95% interval for ``baseline - candidate`` on a loss (positive = better)."""
    y = np.asarray(labels, dtype=int)
    a = np.asarray(candidate, dtype=float)
    b = np.asarray(baseline, dtype=float)
    generator = np.random.default_rng(seed)
    deltas: list[float] = []
    for _ in range(iterations):
        idx = generator.integers(0, len(y), len(y))
        if y[idx].sum() in (0, len(idx)):
            continue
        sample = y[idx].tolist()
        deltas.append(
            evaluate_probabilities(sample, b[idx].tolist())[metric]
            - evaluate_probabilities(sample, a[idx].tolist())[metric]
        )
    point = (
        evaluate_probabilities(y.tolist(), b.tolist())[metric]
        - evaluate_probabilities(y.tolist(), a.tolist())[metric]
    )
    return {
        "point": float(point),
        "low": float(np.percentile(deltas, 2.5)) if deltas else point,
        "high": float(np.percentile(deltas, 97.5)) if deltas else point,
    }


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


def prior_probabilities(
    examples: Sequence[TrainingExample], prior: float = DEFAULT_PRIOR
) -> list[float]:
    return [prior] * len(examples)


def builder_probabilities(examples: Sequence[TrainingExample]) -> list[float]:
    """Post-#60 builder score: the top-ranked reposter's smoothed repost keep rate.

    Within a recency tier the waterfall sorts by exactly this value, so it is
    the ordering the playlist actually uses (rank order only, not calibrated).
    """
    return [_rate_or_prior(row.features.best_reposter_keep_rate) for row in examples]


def legacy_builder_probabilities(examples: Sequence[TrainingExample]) -> list[float]:
    """Pre-#60 builder score: the top-ranked reposter's raw combined hit rate."""
    return [
        _rate_or_prior(row.features.best_reposter_legacy_hit_rate) for row in examples
    ]


def combined_heuristic_probabilities(
    examples: Sequence[TrainingExample],
) -> list[float]:
    """The hand-built evidence from the reposts-builder analysis as one score."""
    output: list[float] = []
    for example in examples:
        f = example.features
        probability = DEFAULT_PRIOR
        probability += 0.12 if f.followed_uploader else -0.03
        probability += 0.04 if f.top200_reposter_count >= 2 else -0.05
        probability += 0.06 if (f.best_reposter_rank or 10_000) <= 75 else -0.05
        unknown_single = f.reposter_count <= 1 and f.reposter_keep_rate is None
        long_track = (f.duration_ms or 0) > 240_000
        if unknown_single and long_track and not f.followed_uploader:
            probability = 0.03
        output.append(min(0.95, max(0.01, probability)))
    return output


def without_features(
    examples: Sequence[TrainingExample], fields: Iterable[str]
) -> list[TrainingExample]:
    """Ablation dataset with the selected semantic fields reset to unknown."""
    defaults: dict[str, Any] = asdict(TrackFeatures())
    updates = {field: defaults[field] for field in fields}
    return [
        replace(example, features=replace(example.features, **updates))
        for example in examples
    ]


ABLATION_GROUPS: dict[str, tuple[str, ...]] = {
    "duration": ("duration_ms",),
    "uploader": ("followed_uploader", "uploader_rank"),
    "reposter_counts": ("reposter_count", "top200_reposter_count"),
    "rank_signals": ("uploader_rank", "best_reposter_rank", "top200_reposter_count"),
    "historical_rates": (
        "uploader_keep_rate",
        "uploader_rated_count",
        "reposter_keep_rate",
        "reposter_rated_count",
    ),
    "event_type": ("event_type",),
    "genre": ("genre",),
    "title": ("title",),
    "age_and_lag": ("release_age_days", "repost_lag_days"),
}


# ---------------------------------------------------------------------------
# Full evaluation
# ---------------------------------------------------------------------------


def _system_report(
    labels: Sequence[int], predictions: Sequence[float], iterations: int
) -> dict[str, Any]:
    bins = calibration_bins(labels, predictions)
    return {
        "metrics": evaluate_probabilities(labels, predictions),
        "confidence_intervals": bootstrap_confidence_intervals(
            labels, predictions, iterations=iterations
        ),
        "calibration": bins,
        "expected_calibration_error": expected_calibration_error(bins),
    }


def _ablation_report(
    split: DatasetSplit, genres: Sequence[str], c: float, version: str
) -> dict[str, dict[str, float]]:
    labels = [row.label for row in split.test]
    fit_rows = [*split.train, *split.validation]
    output: dict[str, dict[str, float]] = {}
    for name, fields in ABLATION_GROUPS.items():
        artifact = fit_model(
            without_features(fit_rows, fields),
            f"{version}-without-{name}",
            regularization_c=c,
            common_genres=genres,
        )
        predictions = score_examples(artifact, without_features(split.test, fields))
        output[name] = evaluate_probabilities(labels, predictions)
    return output


SHIP_GATE_CHECKS: tuple[str, ...] = (
    "brier beats prior with CI above zero",
    "log loss beats prior with CI above zero",
    "precision@50 beats current builder",
    "bottom decile below base rate",
)


def ship_gate(
    model: dict[str, float],
    prior: dict[str, float],
    builder: dict[str, float],
    brier_delta: dict[str, float],
    logloss_delta: dict[str, float],
) -> tuple[bool, list[str]]:
    """Explicit criteria; every failed check is listed in the report."""
    outcomes = (
        brier_delta["low"] > 0,
        logloss_delta["low"] > 0,
        model["precision_at_50"] > builder["precision_at_50"],
        model["bottom_decile_keep_rate"] < prior["base_keep_rate"],
    )
    failed = [name for name, passed in zip(SHIP_GATE_CHECKS, outcomes) if not passed]
    return not failed, failed


def _paired_deltas(
    labels: Sequence[int], systems: dict[str, list[float]], iterations: int
) -> dict[str, dict[str, float]]:
    return {
        f"{metric}_vs_{baseline}": paired_bootstrap_delta(
            labels,
            systems["logistic_regression"],
            systems[baseline],
            metric,
            iterations=iterations,
        )
        for metric in ("brier_score", "log_loss")
        for baseline in ("prior", "current_builder", "combined_heuristic")
    }


def _split_summary(split: DatasetSplit) -> dict[str, Any]:
    labels = [row.label for row in split.test]
    return {
        "strategy": "chronological 60/20/20, decision groups kept whole",
        "train": len(split.train),
        "validation": len(split.validation),
        "test": len(split.test),
        "train_end": split.train[-1].decided_at,
        "validation_end": split.validation[-1].decided_at,
        "test_end": split.test[-1].decided_at,
        "test_keep_rate": float(np.mean(labels)),
    }


def evaluate_model(
    examples: Sequence[TrainingExample],
    version: str,
    bootstrap_iterations: int = 1_000,
    extra_systems: dict[str, list[float]] | None = None,
) -> tuple[ModelArtifact, dict[str, Any]]:
    """Chronological, leakage-safe offline evaluation against the baselines.

    ``extra_systems`` maps a system name to precomputed probabilities over
    ``split.test`` (same order), e.g. cached Jev predictions; they join the
    comparison tables but never the ship gate.
    """
    split = chronological_split(examples)
    genres = select_common_genres(split.train)
    c, grid = select_regularization(split.train, split.validation, genres)
    validation_metrics = evaluate_probabilities(
        [row.label for row in split.validation],
        score_examples(fit_model(split.train, version, c, genres), split.validation),
    )
    candidate = fit_model(
        [*split.train, *split.validation], version, c, genres, validation_metrics
    )
    labels = [row.label for row in split.test]
    systems = {
        "logistic_regression": score_examples(candidate, split.test),
        "prior": prior_probabilities(split.test),
        "current_builder": builder_probabilities(split.test),
        "legacy_builder": legacy_builder_probabilities(split.test),
        "combined_heuristic": combined_heuristic_probabilities(split.test),
    }
    for name, predictions in (extra_systems or {}).items():
        if len(predictions) != len(split.test):
            raise ValueError(
                f"extra system {name!r} has {len(predictions)} predictions "
                f"for {len(split.test)} test examples"
            )
        systems[name] = predictions
    comparisons = {
        name: _system_report(labels, predictions, bootstrap_iterations)
        for name, predictions in systems.items()
    }
    deltas = _paired_deltas(labels, systems, bootstrap_iterations)
    passed, failed = ship_gate(
        comparisons["logistic_regression"]["metrics"],
        comparisons["prior"]["metrics"],
        comparisons["current_builder"]["metrics"],
        deltas["brier_score_vs_prior"],
        deltas["log_loss_vs_prior"],
    )
    report: dict[str, Any] = {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "sample_count": len(examples),
        "positive_count": sum(row.label for row in examples),
        "split": _split_summary(split),
        "decided_at_sources": _count_sources(examples),
        "regularization": {"selected_c": c, "grid": grid},
        "comparisons": comparisons,
        "paired_deltas": deltas,
        "feature_ablations": _ablation_report(split, genres, c, version),
        "coefficients": sorted(
            (
                {"feature": name, "coefficient": value}
                for name, value in zip(candidate.feature_names, candidate.coefficients)
            ),
            key=lambda item: -abs(item["coefficient"]),
        ),
        "intercept": candidate.intercept,
        "ship_gate_passed": passed,
        "ship_gate_failures": failed,
        "recommendation": "ship-shadow" if passed else "no-ship",
    }
    return candidate, report


def _count_sources(examples: Sequence[TrainingExample]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for example in examples:
        counts[example.decided_at_source] = counts.get(example.decided_at_source, 0) + 1
    return dict(sorted(counts.items()))


def artifact_to_json(artifact: ModelArtifact) -> str:
    payload = asdict(artifact)
    for field in ("feature_names", "means", "scales", "coefficients", "common_genres"):
        payload[field] = list(payload[field])
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def artifact_from_json(value: str) -> ModelArtifact:
    payload = json.loads(value)
    for field in ("feature_names", "means", "scales", "coefficients", "common_genres"):
        payload[field] = tuple(payload[field])
    return ModelArtifact(**payload)
