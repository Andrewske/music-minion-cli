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
    expected = {130, 73}  # half-up: 130.01/129.99 -> 130, 72.5 -> 73
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


def _record(track_a_id: int, track_b_id: int, winner_id: int) -> dict:
    response = client.post(
        "/api/comparisons/record",
        json={
            "playlist_id": PLAYLIST_ID,
            "track_a_id": track_a_id,
            "track_b_id": track_b_id,
            "winner_id": winner_id,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _undo(track_a_id: int, track_b_id: int):
    return client.post(
        "/api/comparisons/undo",
        json={"playlist_id": PLAYLIST_ID, "track_a_id": track_a_id, "track_b_id": track_b_id},
    )


def _rating_rows() -> list[tuple]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT track_id, rating, comparison_count, wins, losses"
            " FROM playlist_elo_ratings WHERE playlist_id = ? ORDER BY track_id",
            (PLAYLIST_ID,),
        ).fetchall()
    return [tuple(row) for row in rows]


def test_pair_carries_banner_details() -> None:
    track_ids = _seed_fractional_bpm_playlist()
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE tracks SET key_signature = '8A', released_at = '2025-10-01' WHERE id IN"
            f" ({','.join('?' * len(track_ids))})",
            track_ids,
        )
        conn.commit()

    pair = client.post("/api/comparisons/start", json={"playlist_id": PLAYLIST_ID}).json()["pair"]

    for side in ("track_a", "track_b"):
        assert pair[side]["key_signature"] == "8A"
        assert pair[side]["added_at"] == "2025-10-01"
        assert pair[side]["sc_liked"] is False
        assert pair[side]["soundcloud_url"] is None  # local-only track
        assert pair[side]["reposters"] == []


def test_record_returns_winner_rating_delta() -> None:
    a, b, _ = _seed_fractional_bpm_playlist()

    body = _record(a, b, winner_id=b)

    assert body["rating_delta"] == 16.0  # K=32, equal 1500 ratings


def test_undo_restores_ratings_and_returns_the_pair() -> None:
    a, b, c = _seed_fractional_bpm_playlist()
    _record(a, c, winner_id=a)
    before = _rating_rows()
    _record(a, b, winner_id=b)

    response = _undo(a, b)

    assert response.status_code == 200, response.text
    pair = response.json()["pair"]
    assert {pair["track_a"]["id"], pair["track_b"]["id"]} == {a, b}
    assert _rating_rows() == before
    with get_db_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM playlist_comparison_history WHERE playlist_id = ?",
            (PLAYLIST_ID,),
        ).fetchone()[0]
    assert count == 1


def test_undo_refuses_when_a_later_comparison_used_the_result() -> None:
    a, b, c = _seed_fractional_bpm_playlist()
    _record(a, b, winner_id=a)
    _record(b, c, winner_id=c)

    assert _undo(a, b).status_code == 409
    assert _undo(b, c).status_code == 200
    assert _undo(a, b).status_code == 200  # now it's the latest again
    assert _rating_rows() == []
