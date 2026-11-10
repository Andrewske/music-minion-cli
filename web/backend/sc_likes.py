"""The one SQL definition of "liked on SoundCloud".

Every API that describes a track computes its ``sc_liked`` flag with
``sc_liked_sql`` so the heart means the same thing on every surface. The
sc_likes table is keyed by soundcloud_id, so tracks with no local tracks row
(feed, stories, discovery) resolve too, with one primary-key lookup each.
"""

from collections.abc import Iterable
from typing import Any


def sc_liked_sql(soundcloud_id_expr: str) -> str:
    """SQL boolean: the SoundCloud id in `soundcloud_id_expr` is in sc_likes."""
    return (
        "EXISTS (SELECT 1 FROM sc_likes scl "
        f"WHERE scl.soundcloud_id = {soundcloud_id_expr})"
    )


def liked_soundcloud_ids(conn: Any, soundcloud_ids: Iterable[str | None]) -> set[str]:
    """The subset of `soundcloud_ids` that are in sc_likes (for Python-side joins)."""
    ids = sorted({str(sc_id) for sc_id in soundcloud_ids if sc_id})
    if not ids:
        return set()
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT soundcloud_id FROM sc_likes WHERE soundcloud_id IN ({placeholders})",
        ids,
    ).fetchall()
    return {row[0] for row in rows}
