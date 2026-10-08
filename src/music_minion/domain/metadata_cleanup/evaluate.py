"""Score proposals against gold expectations and render a review report."""

import re
from typing import Any

from music_minion.domain.metadata_cleanup.render import render_title

Row = dict[str, Any]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _name_set(names: list[str]) -> set[str]:
    return {_norm(name).casefold() for name in names if name.strip()}


def compare(expected: Row, proposal: Row) -> dict[str, bool]:
    """Per-field match. Gold TPE1 holds artists + featured, so compare the union."""
    got_title, want_title = _norm(render_title(proposal)), _norm(expected["title"])
    credited = proposal["artists"] + proposal["featured"]
    return {
        "title_exact": got_title == want_title,
        "title_ignore_case": got_title.casefold() == want_title.casefold(),
        "artists": _name_set(credited) == _name_set(expected["credited_artists"]),
        "remixers": _name_set(proposal["remixers"]) == _name_set(expected["remixers"]),
    }


def score(
    gold: list[Row], proposals: dict[str, Row]
) -> tuple[dict[str, Any], list[Row]]:
    """Return (metrics, per-track rows) for every gold track with a proposal."""
    rows = [
        {
            "gold": g,
            "proposal": proposals[g["id"]],
            "match": compare(g["expected"], proposals[g["id"]]),
        }
        for g in gold
        if g["id"] in proposals
    ]
    fields = ("title_exact", "title_ignore_case", "artists", "remixers")
    metrics: dict[str, Any] = {"scored": len(rows), "missing": len(gold) - len(rows)}
    for field in fields:
        hits = sum(row["match"][field] for row in rows)
        metrics[field] = round(hits / len(rows), 3) if rows else 0.0
    metrics["all_ignore_case"] = _all_rate(rows)
    return metrics, rows


def _all_rate(rows: list[Row]) -> float:
    keys = ("title_ignore_case", "artists", "remixers")
    hits = sum(all(row["match"][key] for key in keys) for row in rows)
    return round(hits / len(rows), 3) if rows else 0.0


def _raw_title(gold: Row) -> str:
    sc = gold.get("soundcloud") or {}
    return f"{sc.get('title', gold['filename'])}  [uploader: {sc.get('uploader', '?')}]"


def render_mismatch(row: Row) -> str:
    gold, got, want = row["gold"], row["proposal"], row["gold"]["expected"]
    failed = [
        key for key, ok in row["match"].items() if not ok and key != "title_exact"
    ]
    return "\n".join([
        f"## {gold['id']}   (failed: {', '.join(failed)}; conf {got['confidence']})",
        f"  raw:       {_raw_title(gold)}",
        f"  title      gold: {want['title']}",
        f"             got:  {render_title(got)}",
        f"  artists    gold: {'; '.join(want['credited_artists'])}",
        f"             got:  {'; '.join(got['artists'])}  ft. {'; '.join(got['featured']) or '-'}",
        f"  remixers   gold: {'; '.join(want['remixers']) or '-'}",
        f"             got:  {'; '.join(got['remixers']) or '-'}",
        f"  notes: {got['notes']}",
    ])  # fmt: skip


def render_report(metrics: dict[str, Any], rows: list[Row]) -> str:
    header = "\n".join(f"{key}: {value}" for key, value in metrics.items())
    keys = ("title_ignore_case", "artists", "remixers")
    misses = [row for row in rows if not all(row["match"][key] for key in keys)]
    body = "\n\n".join(render_mismatch(row) for row in misses)
    return f"{header}\n\nMismatches ({len(misses)})\n\n{body}\n"
