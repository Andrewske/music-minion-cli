"""Pure, versioned keep-probability model primitives.

The database-facing orchestration lives in :mod:`preference_scoring`.  Keeping
the feature and model functions here free of database state makes offline
evaluation and production scoring use exactly the same implementation.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

FEATURE_SCHEMA_VERSION = "keep-v1"
DEFAULT_PRIOR = 0.22
UNKNOWN_GENRE = "other"


@dataclass(frozen=True)
class TrackFeatures:
    """Information that was known when a track was surfaced.

    Rates must be calculated only from decisions strictly before ``as_of``.
    Callers should persist this structure with the decision so later metadata
    changes cannot alter historical training examples.
    """

    duration_ms: int | None = None
    followed_uploader: bool = False
    uploader_rank: int | None = None
    reposter_count: int = 0
    best_reposter_rank: int | None = None
    uploader_keep_rate: float | None = None
    uploader_rated_count: float = 0.0
    reposter_keep_rate: float | None = None
    reposter_rated_count: float = 0.0
    event_type: str = "repost"
    genre: str | None = None
    title: str = ""
    release_age_days: float | None = None
    repost_lag_days: float | None = None
    as_of: str | None = None


@dataclass(frozen=True)
class TrainingExample:
    soundcloud_id: str
    decided_at: str
    label: int
    features: TrackFeatures


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
    feature_names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float
    common_genres: tuple[str, ...]
    validation_metrics: dict[str, float]


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


def _safe_rate(rate: float | None) -> float:
    if rate is None or not math.isfinite(rate):
        return DEFAULT_PRIOR
    # Existing artist rates were historically percentages. Accept both forms.
    return min(1.0, max(0.0, rate / 100.0 if rate > 1.0 else rate))


def feature_dict(
    features: TrackFeatures, common_genres: Sequence[str]
) -> dict[str, float]:
    """Convert semantic features to the model's numeric feature mapping."""
    duration_minutes = (features.duration_ms or 0) / 60_000
    title = features.title.lower()
    genre = normalize_genre(features.genre)
    event_type = (
        features.event_type
        if features.event_type in {"release", "repost", "both"}
        else "repost"
    )
    result = {
        "duration_minutes": duration_minutes,
        "duration_missing": float(features.duration_ms is None),
        "duration_over_4m": float(duration_minutes > 4),
        "duration_over_10m": float(duration_minutes > 10),
        "followed_uploader": float(features.followed_uploader),
        "uploader_rank": float(features.uploader_rank or 0),
        "uploader_rank_missing": float(features.uploader_rank is None),
        "reposter_count": float(max(0, features.reposter_count)),
        "best_reposter_rank": float(features.best_reposter_rank or 0),
        "best_reposter_rank_missing": float(features.best_reposter_rank is None),
        "uploader_keep_rate": _safe_rate(features.uploader_keep_rate),
        "uploader_rate_missing": float(features.uploader_keep_rate is None),
        "log_uploader_samples": math.log1p(max(0.0, features.uploader_rated_count)),
        "reposter_keep_rate": _safe_rate(features.reposter_keep_rate),
        "reposter_rate_missing": float(features.reposter_keep_rate is None),
        "log_reposter_samples": math.log1p(max(0.0, features.reposter_rated_count)),
        "event_release": float(event_type in {"release", "both"}),
        "event_repost": float(event_type in {"repost", "both"}),
        "event_both": float(event_type == "both"),
        "title_mix": float("mix" in title or "radio" in title or "podcast" in title),
        "title_remix": float("remix" in title or "refix" in title or "edit" in title),
        "release_age_days": float(features.release_age_days or 0),
        "release_age_missing": float(features.release_age_days is None),
        "repost_lag_days": float(features.repost_lag_days or 0),
        "repost_lag_missing": float(features.repost_lag_days is None),
    }
    for known_genre in common_genres:
        result[f"genre={known_genre}"] = float(genre == known_genre)
    result[f"genre={UNKNOWN_GENRE}"] = float(genre not in common_genres)
    return result


def chronological_split(
    examples: Sequence[TrainingExample],
    train_fraction: float = 0.60,
    validation_fraction: float = 0.20,
) -> DatasetSplit:
    """Stable chronological split; equal timestamps use SoundCloud ID."""
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1:
        raise ValueError("split fractions must be between zero and one")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("train + validation fraction must be below one")
    ordered = sorted(examples, key=lambda row: (row.decided_at, row.soundcloud_id))
    if len(ordered) < 5:
        raise ValueError("at least five definitive decisions are required")
    train_end = max(1, int(len(ordered) * train_fraction))
    validation_end = max(
        train_end + 1, int(len(ordered) * (train_fraction + validation_fraction))
    )
    validation_end = min(validation_end, len(ordered) - 1)
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
    validation_metrics: dict[str, float] | None = None,
    common_genres: Sequence[str] | None = None,
) -> ModelArtifact:
    """Fit deterministic L2 logistic regression and return a portable artifact."""
    if not examples:
        raise ValueError("cannot train without examples")
    if {example.label for example in examples} != {0, 1}:
        raise ValueError("training data must contain both keep and nope labels")
    genres = tuple(common_genres or select_common_genres(examples))
    matrix, labels, names = _matrix(examples, genres)
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0)
    scales[scales == 0] = 1.0
    standardized = (matrix - means) / scales
    estimator = LogisticRegression(
        C=1.0,
        class_weight=None,
        max_iter=2_000,
        random_state=0,
        solver="lbfgs",
    )
    estimator.fit(standardized, labels)
    ordered = sorted(examples, key=lambda row: (row.decided_at, row.soundcloud_id))
    return ModelArtifact(
        version=version,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        trained_at=datetime.now(timezone.utc).isoformat(),
        training_start=ordered[0].decided_at,
        training_end=ordered[-1].decided_at,
        sample_count=len(examples),
        positive_count=int(labels.sum()),
        feature_names=names,
        means=tuple(float(value) for value in means),
        scales=tuple(float(value) for value in scales),
        coefficients=tuple(float(value) for value in estimator.coef_[0]),
        intercept=float(estimator.intercept_[0]),
        common_genres=genres,
        validation_metrics=dict(validation_metrics or {}),
    )


def score_features(artifact: ModelArtifact, features: TrackFeatures) -> float:
    row = feature_dict(features, artifact.common_genres)
    values = np.asarray(
        [row.get(name, 0.0) for name in artifact.feature_names], dtype=float
    )
    standardized = (values - np.asarray(artifact.means)) / np.asarray(artifact.scales)
    logit = artifact.intercept + float(
        np.dot(standardized, np.asarray(artifact.coefficients))
    )
    # Numerically stable sigmoid.
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    exp_logit = math.exp(logit)
    return exp_logit / (1.0 + exp_logit)


def score_examples(
    artifact: ModelArtifact, examples: Sequence[TrainingExample]
) -> list[float]:
    return [score_features(artifact, example.features) for example in examples]


def evaluate_probabilities(
    labels: Sequence[int], probabilities: Sequence[float]
) -> dict[str, float]:
    if not labels or len(labels) != len(probabilities):
        raise ValueError("labels and probabilities must be non-empty and aligned")
    y = np.asarray(labels, dtype=int)
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-9, 1 - 1e-9)
    order = np.argsort(-p)
    top_count = min(100, len(y))
    bottom_count = max(1, math.ceil(len(y) / 10))
    return {
        "sample_count": float(len(y)),
        "base_keep_rate": float(y.mean()),
        "brier_score": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "precision_at_100": float(y[order[:top_count]].mean()),
        "bottom_decile_keep_rate": float(y[order[-bottom_count:]].mean()),
    }


def calibration_bins(
    labels: Sequence[int], probabilities: Sequence[float], bins: int = 10
) -> list[dict[str, float]]:
    y = np.asarray(labels, dtype=int)
    p = np.asarray(probabilities, dtype=float)
    output: list[dict[str, float]] = []
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        mask = (p >= low) & (p <= high if index == bins - 1 else p < high)
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


def bootstrap_confidence_intervals(
    labels: Sequence[int],
    probabilities: Sequence[float],
    iterations: int = 1_000,
    seed: int = 0,
) -> dict[str, tuple[float, float]]:
    """Return deterministic 95% bootstrap intervals for evaluation metrics."""
    y = np.asarray(labels, dtype=int)
    p = np.asarray(probabilities, dtype=float)
    if len(y) < 2:
        return {}
    generator = np.random.default_rng(seed)
    samples: dict[str, list[float]] = {}
    for _ in range(iterations):
        indices = generator.integers(0, len(y), len(y))
        metrics = evaluate_probabilities(y[indices].tolist(), p[indices].tolist())
        for name, value in metrics.items():
            if name != "sample_count":
                samples.setdefault(name, []).append(value)
    return {
        name: (float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5)))
        for name, values in samples.items()
    }


def prior_probabilities(
    examples: Sequence[TrainingExample], prior: float = DEFAULT_PRIOR
) -> list[float]:
    return [prior] * len(examples)


def builder_probabilities(examples: Sequence[TrainingExample]) -> list[float]:
    """Monotonic proxy for the current rank/hit-rate builder ordering."""
    output: list[float] = []
    for example in examples:
        features = example.features
        rank = features.best_reposter_rank or 1_000
        rate = _safe_rate(features.reposter_keep_rate)
        output.append(min(0.95, max(0.01, 0.7 * rate + 0.3 / math.sqrt(rank))))
    return output


def combined_heuristic_probabilities(
    examples: Sequence[TrainingExample],
) -> list[float]:
    """Reproduce the pre-model evidence as a transparent comparison baseline."""
    output: list[float] = []
    for example in examples:
        f = example.features
        probability = DEFAULT_PRIOR
        probability += 0.12 if f.followed_uploader else -0.03
        probability += 0.04 if f.reposter_count >= 2 else -0.01
        probability += 0.06 if (f.best_reposter_rank or 10_000) <= 75 else -0.05
        if (
            f.reposter_count <= 1
            and f.best_reposter_rank is None
            and (f.duration_ms or 0) > 240_000
        ):
            probability = 0.03
        output.append(min(0.95, max(0.01, probability)))
    return output


def without_features(
    examples: Sequence[TrainingExample], fields: Iterable[str]
) -> list[TrainingExample]:
    """Return an ablation dataset with selected semantic fields set unknown."""
    defaults: dict[str, Any] = {
        "duration_ms": None,
        "followed_uploader": False,
        "uploader_rank": None,
        "reposter_count": 0,
        "best_reposter_rank": None,
        "uploader_keep_rate": None,
        "uploader_rated_count": 0.0,
        "reposter_keep_rate": None,
        "reposter_rated_count": 0.0,
        "event_type": "repost",
        "genre": None,
        "title": "",
        "release_age_days": None,
        "repost_lag_days": None,
    }
    updates = {field: defaults[field] for field in fields}
    return [
        replace(example, features=replace(example.features, **updates))
        for example in examples
    ]


def artifact_to_json(artifact: ModelArtifact) -> str:
    payload = asdict(artifact)
    payload["feature_names"] = list(artifact.feature_names)
    payload["means"] = list(artifact.means)
    payload["scales"] = list(artifact.scales)
    payload["coefficients"] = list(artifact.coefficients)
    payload["common_genres"] = list(artifact.common_genres)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def artifact_from_json(value: str) -> ModelArtifact:
    payload = json.loads(value)
    for field in ("feature_names", "means", "scales", "coefficients", "common_genres"):
        payload[field] = tuple(payload[field])
    return ModelArtifact(**payload)


def explanation(features: TrackFeatures) -> str:
    """Short, stable explanation made only from observable source features."""
    parts: list[str] = []
    if features.followed_uploader:
        parts.append("followed uploader")
    if features.reposter_count:
        suffix = "reposter" if features.reposter_count == 1 else "reposters"
        parts.append(f"{features.reposter_count} {suffix}")
    if features.best_reposter_rank is not None:
        parts.append(f"best rank #{features.best_reposter_rank}")
    if features.duration_ms:
        total_seconds = round(features.duration_ms / 1_000)
        parts.append(f"{total_seconds // 60}:{total_seconds % 60:02d}")
    return " · ".join(parts) or "limited history"


def evaluate_model(
    examples: Sequence[TrainingExample],
    version: str,
    bootstrap_iterations: int = 1_000,
) -> tuple[ModelArtifact, dict[str, Any]]:
    """Run the complete chronological, leakage-safe offline evaluation."""
    split = chronological_split(examples)
    genres = select_common_genres(split.train)
    candidate = fit_model(split.train, version, common_genres=genres)
    validation_labels = [row.label for row in split.validation]
    test_labels = [row.label for row in split.test]
    validation_predictions = score_examples(candidate, split.validation)
    validation_metrics = evaluate_probabilities(
        validation_labels, validation_predictions
    )
    candidate = replace(candidate, validation_metrics=validation_metrics)

    systems = {
        "logistic_regression": score_examples(candidate, split.test),
        "prior": prior_probabilities(split.test),
        "current_builder": builder_probabilities(split.test),
        "combined_heuristic": combined_heuristic_probabilities(split.test),
    }
    comparisons: dict[str, Any] = {}
    for name, predictions in systems.items():
        comparisons[name] = {
            "metrics": evaluate_probabilities(test_labels, predictions),
            "confidence_intervals": bootstrap_confidence_intervals(
                test_labels,
                predictions,
                iterations=bootstrap_iterations,
                seed=0,
            ),
            "calibration": calibration_bins(test_labels, predictions),
        }

    ablation_groups = {
        "duration": ("duration_ms",),
        "uploader": (
            "followed_uploader",
            "uploader_rank",
            "uploader_keep_rate",
            "uploader_rated_count",
        ),
        "reposters": (
            "reposter_count",
            "best_reposter_rank",
            "reposter_keep_rate",
            "reposter_rated_count",
        ),
        "event_type": ("event_type",),
        "genre": ("genre",),
        "title": ("title",),
        "age_and_lag": ("release_age_days", "repost_lag_days"),
    }
    ablations: dict[str, dict[str, float]] = {}
    for name, fields in ablation_groups.items():
        train = without_features(split.train, fields)
        test = without_features(split.test, fields)
        artifact = fit_model(train, f"{version}-without-{name}", common_genres=genres)
        ablations[name] = evaluate_probabilities(
            test_labels, score_examples(artifact, test)
        )

    model_metrics = comparisons["logistic_regression"]["metrics"]
    prior_metrics = comparisons["prior"]["metrics"]
    ship = (
        model_metrics["brier_score"] < prior_metrics["brier_score"]
        and model_metrics["log_loss"] < prior_metrics["log_loss"]
        and model_metrics["precision_at_100"] >= prior_metrics["precision_at_100"]
    )
    coefficients = sorted(
        zip(candidate.feature_names, candidate.coefficients),
        key=lambda item: abs(item[1]),
        reverse=True,
    )
    report: dict[str, Any] = {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "split": {
            "strategy": "chronological 60/20/20",
            "train": len(split.train),
            "validation": len(split.validation),
            "test": len(split.test),
            "train_end": split.train[-1].decided_at,
            "validation_end": split.validation[-1].decided_at,
        },
        "comparisons": comparisons,
        "feature_ablations": ablations,
        "coefficients": [
            {"feature": name, "coefficient": value} for name, value in coefficients
        ],
        "cold_start": {
            "numeric": "missing indicators are set and values fall back to zero before standardization",
            "artist_rates": f"missing rates use the {DEFAULT_PRIOR:.0%} population prior",
            "genre": "missing and rare genres are grouped into genre=other",
            "artist_ids": "raw artist IDs are never model features",
        },
        "limitations": [
            "Historical decisions without contemporaneous feature snapshots are excluded.",
            "Offline outcomes may not capture tracks the user would keep if never surfaced.",
            "Confidence intervals describe this chronological test window, not future drift.",
        ],
        "recommendation": "ship-shadow-only" if ship else "do-not-ship",
        "ship_gate_passed": ship,
    }
    return candidate, report
