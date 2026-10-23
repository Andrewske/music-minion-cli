"""Comparison endpoints must work with fractional (Serato) BPMs."""

from fastapi.testclient import TestClient

from music_minion.core.database import get_db_connection
from web.backend.main import app

client = TestClient(app)

FRACTIONAL_BPMS = (130.01, 72.5, 129.99)
PLAYLIST_ID = 414


def _seed_fractional_bpm_playlist() -> list[int]:
    """Insert a playlist whose tracks all have fractional BPMs."""
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO playlists (id, name, type) VALUES (?, 'Bday 26', 'manual')",
            (PLAYLIST_ID,),
        )
        track_ids = []
        for i, bpm in enumerate(FRACTIONAL_BPMS):
            cursor = conn.execute(
                "INSERT INTO tracks (title, artist, local_path, source, bpm)"
                " VALUES (?, 'Artist', ?, 'local', ?)",
                (f"Track {i}", f"/music/track-{i}.mp3", bpm),
            )
            track_ids.append(cursor.lastrowid)
            conn.execute(
                "INSERT INTO playlist_tracks (playlist_id, track_id, position)"
                " VALUES (?, ?, ?)",
                (PLAYLIST_ID, cursor.lastrowid, i),
            )
        conn.commit()
    return track_ids


def _stored_bpms(track_ids: list[int]) -> list[float]:
    placeholders = ",".join("?" * len(track_ids))
    with get_db_connection() as conn:
        rows = conn.execute(
            f"SELECT bpm FROM tracks WHERE id IN ({placeholders}) ORDER BY id",
            track_ids,
        ).fetchall()
    return [row["bpm"] for row in rows]


def _assert_rounded_pair(pair: dict) -> None:
    expected = {round(bpm) for bpm in FRACTIONAL_BPMS}
    for side in ("track_a", "track_b"):
        assert isinstance(pair[side]["bpm"], int)
        assert pair[side]["bpm"] in expected


def test_start_and_record_with_fractional_bpm() -> None:
    track_ids = _seed_fractional_bpm_playlist()

    start = client.post("/api/comparisons/start", json={"playlist_id": PLAYLIST_ID})
    assert start.status_code == 200, start.text
    pair = start.json()["pair"]
    _assert_rounded_pair(pair)

    track_a_id, track_b_id = pair["track_a"]["id"], pair["track_b"]["id"]
    record = client.post(
        "/api/comparisons/record",
        json={
            "playlist_id": PLAYLIST_ID,
            "track_a_id": track_a_id,
            "track_b_id": track_b_id,
            "winner_id": track_a_id,
        },
    )
    assert record.status_code == 200, record.text
    _assert_rounded_pair(record.json()["pair"])

    # Rounding is display-only: the DB keeps Serato's exact values
    assert _stored_bpms(track_ids) == list(FRACTIONAL_BPMS)
