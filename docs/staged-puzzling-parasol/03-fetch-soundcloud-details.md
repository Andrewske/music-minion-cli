---
task: 03-fetch-soundcloud-details
status: pending
depends: [02-soundcloud-lookup-cascade]
files:
  - path: scripts/enrich_metadata.py
    action: modify
---

# Fetch Full SoundCloud Track Details

## Context
Once we have a SoundCloud track ID, fetch the complete track object from the API. Extract the specific fields needed for AI parsing.

## Files to Modify/Create
- scripts/enrich_metadata.py (modify)

## Implementation Details

### API Call
```python
def fetch_soundcloud_track(soundcloud_id: str, access_token: str) -> dict:
    """Fetch full track details from SoundCloud API."""
    url = f"https://api.soundcloud.com/tracks/{soundcloud_id}"
    headers = {"Authorization": f"OAuth {access_token}"}

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()
```

### Fields to Extract
From the full track object, extract these fields for AI parsing:
```python
{
    "title": track.get("title"),
    "username": track.get("user", {}).get("username"),
    "metadata_artist": track.get("metadata_artist"),
    "description": track.get("description"),
    "genre": track.get("genre"),
    "label_name": track.get("label_name"),
    "release_year": track.get("release_year"),
    "tag_list": track.get("tag_list"),
    "created_at": track.get("created_at"),
}
```

### Auth Token
Use token refresh pattern from `init_provider()`:
```python
from music_minion.domain.library.providers.soundcloud import auth

def get_valid_access_token() -> str | None:
    """Load token, refresh if expired, return access_token or None."""
    token_data = auth._load_user_tokens()
    if not token_data:
        print("❌ Not authenticated. Run: library auth soundcloud")
        return None

    if auth.is_token_expired(token_data):
        refreshed = auth.refresh_token(token_data)
        if not refreshed:
            print("❌ Token expired. Run: library auth soundcloud")
            return None
        token_data = refreshed

    return token_data["access_token"]
```

Call this once at script start, exit early if None.

## Verification
```bash
uv run python scripts/enrich_metadata.py /path/to/track.mp3 --dry-run
```

Expected: Script prints the extracted SoundCloud fields before AI parsing step.
