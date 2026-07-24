#!/usr/bin/env python3
"""Move tracks from one SoundCloud playlist into another (merge), batched.

Use case: an accidental duplicate playlist (e.g. "jun-26-1") needs its tracks
folded into the canonical one (e.g. "jun-26"). Tracks already present in the
target are skipped. Order: existing target tracks first, then new source tracks
in source order.

Strategy: SoundCloud playlist edits are full-list PUT replacements, so we do a
single GET-target / GET-source / merge / PUT-target round trip instead of one
PUT per track.

Usage:
    uv run scripts/move_sc_playlist_tracks.py <source_url> <target_url> [--apply] [--remove-source]

    --apply          Actually PUT changes. Without it, dry-run (prints plan only).
    --remove-source  After merge, also empty the source playlist (PUT []).

Example:
    uv run scripts/move_sc_playlist_tracks.py \
        https://soundcloud.com/kevinbigfoot/sets/jun-26-1 \
        https://soundcloud.com/kevinbigfoot/sets/jun-26 --apply
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import requests
from loguru import logger

from music_minion.domain.library.provider import ProviderConfig, ProviderState
from music_minion.domain.library.providers.soundcloud.api import (
    API_BASE_URL,
    _ensure_valid_token,
    _format_playlist_urn,
    _format_track_urn,
)

SC_PLAYLIST_LIMIT = 500


def load_provider_state() -> ProviderState:
    """Build ProviderState from on-disk SC user tokens."""
    data_home = os.environ.get("XDG_DATA_HOME")
    base = (
        Path(data_home) / "music-minion"
        if data_home
        else Path.home() / ".local" / "share" / "music-minion"
    )
    token_path = base / "soundcloud" / "user_tokens.json"
    if not token_path.exists():
        raise RuntimeError(f"No SC tokens at {token_path} - run `music-minion sc login`")
    token_data = json.loads(token_path.read_text())
    return ProviderState(
        config=ProviderConfig(name="soundcloud"),
        authenticated=True,
        cache={"token_data": token_data},
    )


def auth_headers(state: ProviderState) -> tuple[ProviderState, dict]:
    state, token_data = _ensure_valid_token(state)
    if not token_data:
        raise RuntimeError("Failed to refresh SC token - run `music-minion sc login`")
    return state, {"Authorization": f"OAuth {token_data['access_token']}"}


def resolve_playlist(state: ProviderState, url: str) -> tuple[ProviderState, dict]:
    """Resolve a SC set URL to its playlist JSON (with tracks)."""
    state, headers = auth_headers(state)
    resp = requests.get(
        f"{API_BASE_URL}/resolve", params={"url": url}, headers=headers, timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("kind") != "playlist":
        raise RuntimeError(f"{url} resolved to kind={data.get('kind')!r}, not a playlist")
    # /resolve may not include full track list; fetch by id to be safe
    pid = str(data["id"])
    state, headers = auth_headers(state)
    resp = requests.get(
        f"{API_BASE_URL}/playlists/{_format_playlist_urn(pid)}",
        params={"show_tracks": True},
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    return state, resp.json()


def track_ids(playlist: dict) -> list[str]:
    return [str(t["id"]) for t in playlist.get("tracks", []) if t]


def put_tracks(state: ProviderState, playlist_id: str, ids: list[str]) -> ProviderState:
    state, headers = auth_headers(state)
    payload = {"playlist": {"tracks": [{"urn": _format_track_urn(t)} for t in ids]}}
    resp = requests.put(
        f"{API_BASE_URL}/playlists/{_format_playlist_urn(playlist_id)}",
        headers=headers,
        json=payload,
        timeout=60,
    )
    if not resp.ok:
        logger.error(f"PUT failed {resp.status_code}: {resp.text[:500]}")
        resp.raise_for_status()
    return state


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if len(args) != 2:
        print(__doc__)
        return 2

    source_url, target_url = args
    apply = "--apply" in flags
    remove_source = "--remove-source" in flags

    state = load_provider_state()

    logger.info(f"Resolving source: {source_url}")
    state, source = resolve_playlist(state, source_url)
    logger.info(f"Resolving target: {target_url}")
    state, target = resolve_playlist(state, target_url)

    src_ids = track_ids(source)
    tgt_ids = track_ids(target)
    tgt_set = set(tgt_ids)

    new_ids = [t for t in src_ids if t not in tgt_set]
    already = len(src_ids) - len(new_ids)

    print()
    print(f"Source '{source.get('title')}' (id={source['id']}): {len(src_ids)} tracks")
    print(f"Target '{target.get('title')}' (id={target['id']}): {len(tgt_ids)} tracks")
    print(f"  → {len(new_ids)} new to add, {already} already present (skipped)")

    merged = tgt_ids + new_ids
    if len(merged) > SC_PLAYLIST_LIMIT:
        logger.warning(
            f"Merged size {len(merged)} exceeds SC hard limit {SC_PLAYLIST_LIMIT}; "
            "SC will likely reject the PUT. Split needed."
        )

    if not new_ids and not remove_source:
        print("\nNothing to do — all source tracks already in target.")
        return 0

    if not apply:
        print("\n[DRY RUN] No changes made. Re-run with --apply to commit.")
        if remove_source:
            print("[DRY RUN] Would also empty source playlist.")
        return 0

    print(f"\nApplying: target → {len(merged)} tracks")
    state = put_tracks(state, str(target["id"]), merged)
    print("✓ Target updated.")

    if remove_source:
        print("Emptying source playlist...")
        state = put_tracks(state, str(source["id"]), [])
        print("✓ Source emptied (delete it from the SC web UI if desired).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
