"""Markdown rendering for the offline keep-model evaluation report."""

from __future__ import annotations

from typing import Any, Sequence

from web.backend.preference_model import SHIP_GATE_CHECKS

SYSTEM_LABELS: dict[str, str] = {
    "logistic_regression": "Logistic regression",
    "prior": "22% prior",
    "current_builder": "Current builder (best reposter keep rate)",
    "legacy_builder": "Legacy builder (combined hit_rate)",
    "combined_heuristic": "Reported combined heuristic",
}

METRIC_COLUMNS: tuple[tuple[str, str], ...] = (
    ("brier_score", "Brier"),
    ("log_loss", "Log loss"),
    ("auc", "AUC"),
    ("precision_at_20", "P@20"),
    ("precision_at_50", "P@50"),
    ("precision_at_100", "P@100"),
    ("bottom_decile_keep_rate", "Bottom-decile keep"),
)


def _fmt(value: float | None, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _ci(intervals: dict[str, Sequence[float]], metric: str) -> str:
    bounds = intervals.get(metric)
    if not bounds:
        return ""
    return f" [{bounds[0]:.3f}, {bounds[1]:.3f}]"


def _comparison_table(comparisons: dict[str, Any]) -> list[str]:
    header = (
        "| System | " + " | ".join(label for _, label in METRIC_COLUMNS) + " | ECE |"
    )
    lines = [header, "|---|" + "---:|" * (len(METRIC_COLUMNS) + 1)]
    for name, block in comparisons.items():
        metrics, intervals = block["metrics"], block["confidence_intervals"]
        cells = [
            f"{_fmt(metrics[key])}{_ci(intervals, key)}" for key, _ in METRIC_COLUMNS
        ]
        lines.append(
            f"| {SYSTEM_LABELS.get(name, name)} | "
            + " | ".join(cells)
            + f" | {_fmt(block['expected_calibration_error'])} |"
        )
    return lines


def _delta_table(deltas: dict[str, dict[str, float]]) -> list[str]:
    lines = [
        "| Comparison | Improvement (baseline − model) | 95% CI |",
        "|---|---:|---:|",
    ]
    for name, delta in deltas.items():
        lines.append(
            f"| {name.replace('_', ' ')} | {delta['point']:+.4f} | "
            f"[{delta['low']:+.4f}, {delta['high']:+.4f}] |"
        )
    return lines


def _calibration_table(bins: Sequence[dict[str, float]]) -> list[str]:
    lines = [
        "| Predicted bin | n | Mean prediction | Observed keep rate |",
        "|---|---:|---:|---:|",
    ]
    for item in bins:
        lines.append(
            f"| {item['low']:.1f}–{item['high']:.1f} | {item['count']:.0f} | "
            f"{item['mean_prediction']:.3f} | {item['keep_rate']:.3f} |"
        )
    return lines


def _ablation_table(
    full: dict[str, float], ablations: dict[str, dict[str, float]]
) -> list[str]:
    lines = [
        "| Removed group | Brier | Δ Brier | Log loss | Δ log loss | AUC | P@50 |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| (none) | {_fmt(full['brier_score'])} | — | {_fmt(full['log_loss'])} | — | "
        f"{_fmt(full['auc'])} | {_fmt(full['precision_at_50'])} |",
    ]
    for name, metrics in ablations.items():
        lines.append(
            f"| {name} | {_fmt(metrics['brier_score'])} | "
            f"{metrics['brier_score'] - full['brier_score']:+.4f} | "
            f"{_fmt(metrics['log_loss'])} | {metrics['log_loss'] - full['log_loss']:+.4f} | "
            f"{_fmt(metrics['auc'])} | {_fmt(metrics['precision_at_50'])} |"
        )
    return lines


def _coefficient_table(
    coefficients: Sequence[dict[str, Any]], limit: int = 25
) -> list[str]:
    lines = ["| Feature (standardized) | Coefficient |", "|---|---:|"]
    for item in coefficients[:limit]:
        lines.append(f"| `{item['feature']}` | {item['coefficient']:+.3f} |")
    return lines


def _grid_table(grid: Sequence[dict[str, float]]) -> list[str]:
    lines = [
        "| C | Validation log loss | Validation Brier | Validation AUC |",
        "|---|---:|---:|---:|",
    ]
    for row in grid:
        lines.append(
            f"| {row['c']} | {_fmt(row['log_loss'])} | {_fmt(row['brier_score'])} | {_fmt(row['auc'])} |"
        )
    return lines


COLD_START_NOTES: tuple[str, ...] = (
    "Unknown uploader (no SoundCloud ID, upload event, or name match): "
    "`followed_uploader = 0`, uploader rank treated as outside the top 200 "
    "with `uploader_rank_missing = 1`, uploader rate falls back to the 22% prior "
    "with `uploader_rate_missing = 1`.",
    "Artist never rated in a role: rate is the prior and the `*_rate_missing` "
    "indicator is set, so the model can learn that 'unknown' differs from "
    "'measured at 22%'.",
    "No reposters known at decision time: `reposter_count = 0`, best reposter "
    "rank treated as missing (worst band).",
    "Missing duration, release date, or repost time: value filled with a "
    "neutral zero plus a missing indicator.",
    "Genre: missing and rare values collapse into `genre=other`; only genres "
    "with 10+ training rows get their own indicator.",
    "Raw artist IDs are never features, so an unseen artist scores from its "
    "rank, follow state, and role statistics alone.",
)


def render_evaluation_markdown(
    report: dict[str, Any], limitations: Sequence[str], db_label: str
) -> str:
    """Complete report; the recommendation paragraph is data-driven."""
    model = report["comparisons"]["logistic_regression"]
    split = report["split"]
    verdict = "SHIP (shadow mode first)" if report["ship_gate_passed"] else "NO-SHIP"
    lines = [
        "# Keep-probability model: offline evaluation",
        "",
        f"Source: `{db_label}` · feature schema `{report['feature_schema_version']}` · "
        "generated by `uv run python scripts/evaluate_keep_model.py`.",
        "",
        f"## Recommendation: {verdict}",
        "",
        *_recommendation_paragraph(report),
        "",
        "## Data and splits",
        "",
        f"- Decided tracks: {report['sample_count']} "
        f"({report['positive_count']} keeps, "
        f"{report['positive_count'] / max(1, report['sample_count']):.1%})",
        f"- Split: {split['strategy']} → train {split['train']} / "
        f"validation {split['validation']} / test {split['test']} "
        f"(test keep rate {split['test_keep_rate']:.1%})",
        f"- Train ends {split['train_end']}, validation ends {split['validation_end']}, "
        f"test ends {split['test_end']}",
        f"- Decision-time sources: {report['decided_at_sources']}",
        f"- Regularization: L2, C = {report['regularization']['selected_c']} "
        "chosen by validation log loss, then refit on train + validation",
        "",
        "## Test-set comparison (95% bootstrap CIs)",
        "",
        *_comparison_table(report["comparisons"]),
        "",
        "Builder baselines are orderings, not calibrated probabilities; read their",
        "precision and bottom-decile columns, not their Brier or log loss.",
        "",
        "### Paired improvements of the model over baselines",
        "",
        *_delta_table(report["paired_deltas"]),
        "",
        "## Calibration (model, test set)",
        "",
        *_calibration_table(model["calibration"]),
        "",
        f"Expected calibration error: {model['expected_calibration_error']:.3f}",
        "",
        "## Feature ablations (refit without the group, scored on test)",
        "",
        *_ablation_table(model["metrics"], report["feature_ablations"]),
        "",
        "## Regularization grid (validation set)",
        "",
        *_grid_table(report["regularization"]["grid"]),
        "",
        "## Coefficients",
        "",
        f"Intercept {report['intercept']:+.3f}. Features are standardized, so a",
        "coefficient is the log-odds change per one standard deviation.",
        "",
        *_coefficient_table(report["coefficients"]),
        "",
        "## Cold-start behavior",
        "",
        *[f"- {note}" for note in COLD_START_NOTES],
        "",
        "## Ship gate",
        "",
        *[
            f"- {'FAIL' if name in report['ship_gate_failures'] else 'PASS'}: {name}"
            for name in SHIP_GATE_CHECKS
        ],
        "",
        "## Limitations",
        "",
        *[f"- {item}" for item in limitations],
        "",
    ]
    return "\n".join(lines)


def _recommendation_paragraph(report: dict[str, Any]) -> list[str]:
    model = report["comparisons"]["logistic_regression"]["metrics"]
    prior = report["comparisons"]["prior"]["metrics"]
    builder = report["comparisons"]["current_builder"]["metrics"]
    brier = report["paired_deltas"]["brier_score_vs_prior"]
    return [
        f"On the held-out chronological test window ({int(model['sample_count'])} "
        f"decisions, {prior['base_keep_rate']:.1%} keep rate) the model scores "
        f"Brier {model['brier_score']:.3f} vs {prior['brier_score']:.3f} for the prior "
        f"(paired improvement {brier['point']:+.4f}, 95% CI "
        f"[{brier['low']:+.4f}, {brier['high']:+.4f}]), log loss "
        f"{model['log_loss']:.3f} vs {prior['log_loss']:.3f}, AUC {model['auc']:.3f}. "
        f"Precision@50 is {model['precision_at_50']:.1%} against "
        f"{builder['precision_at_50']:.1%} for the current builder ordering and the "
        f"bottom decile keeps at {model['bottom_decile_keep_rate']:.1%}. "
        + (
            "Every gate check passed, so the model is worth a shadow-mode rollout "
            "(score and log, do not reorder) under ticket #62."
            if report["ship_gate_passed"]
            else "Gate failures: "
            + "; ".join(report["ship_gate_failures"])
            + ". Do not change production selection on this evidence."
        )
    ]
