# CLI Remote Commands

## Files to Modify/Create
- `src/music_minion/config.py` or config handling (modify)
- `src/music_minion/cli/web_commands.py` or equivalent (modify)

## Implementation Details

### Part 1: Add Config Option

Support this in config.toml:

```toml
[web]
remote_server = "https://music.piserver:8443"
```

Add to config loading:

```python
# In config handling
def get_remote_server() -> str | None:
    """Get remote server URL from config, if set."""
    config = get_config()
    return config.get("web", {}).get("remote_server")
```

### Part 2: Modify CLI Web Commands

```python
# src/music_minion/cli/web_commands.py (or equivalent)
import requests
from music_minion.config import get_config

def get_remote_server() -> str | None:
    """Get remote server URL from config, if set."""
    config = get_config()
    web_config = config.get("web", {})
    return web_config.get("remote_server") if isinstance(web_config, dict) else None


def web_winner():
    """Mark track A as winner - local IPC or remote."""
    remote = get_remote_server()

    if remote:
        response = requests.post(
            f"{remote}/api/comparisons/verdict",
            json={
                "session_id": "remote",
                "winner_id": "track_a",
            },
            timeout=5,
        )
        response.raise_for_status()
        print("Winner recorded on remote server")
    else:
        send_ipc_command("winner")


def web_play1():
    """Play track A - local IPC or remote."""
    remote = get_remote_server()
    if remote:
        requests.post(
            f"{remote}/api/comparisons/select-track",
            json={"track_id": "track_a", "is_playing": True},
            timeout=5
        )
        print("Track A selected on remote server")
    else:
        send_ipc_command("play1")


def web_play2():
    """Play track B - local IPC or remote."""
    remote = get_remote_server()
    if remote:
        requests.post(
            f"{remote}/api/comparisons/select-track",
            json={"track_id": "track_b", "is_playing": True},
            timeout=5
        )
        print("Track B selected on remote server")
    else:
        send_ipc_command("play2")
```

### Part 3: Track Alias Resolution

The backend resolves "track_a"/"track_b" strings using `sync_manager.current_comparison` (stateful SyncManager from Task 01). This is already implemented in Task 04's endpoint - no additional code needed here.

**How it works:** SyncManager stores the current comparison pair when a session starts or verdict is recorded. CLI sends `"track_a"` string, backend looks it up from stored state.

## Acceptance Criteria

1. Set `remote_server` in config.toml
2. Run `music-minion web-winner` from CLI
3. Both browser tabs advance to next comparison pair
4. Run `music-minion web-play1`
5. Both browser tabs show Track A selected

## Dependencies

- Task 01-04 (full backend + frontend sync working)

## Commits

```bash
git add src/music_minion/cli/ src/music_minion/config.py
git commit -m "feat(sync): add CLI remote command support"
```
