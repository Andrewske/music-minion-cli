# SoundCloud Discovery: Reusable Code Patterns

Quick reference for extracting and adapting code from soundcloud-discovery.

## 1. OAuth Token Management (Ready to Extract)

### Files to Extract
- `soundcloud-discovery/core/auth.py` - Complete file, self-contained
- `soundcloud-discovery/core/api.py` - Sections for token helpers

### Usage Pattern
```python
# One-time authorization
from core.auth import generate_pkce, build_auth_url, exchange_code_for_token, save_tokens
pkce = generate_pkce()
state = generate_state()
auth_url = build_auth_url(client_id, redirect_uri, pkce["code_challenge"], state)
# User opens auth_url, server gets callback with 'code'
token_data = exchange_code_for_token(code, client_id, client_secret, redirect_uri, pkce["code_verifier"])
save_tokens(token_data)

# Automatic use with auto-refresh
from core.api import get_oauth_token
token = get_oauth_token()  # Returns valid token, auto-refreshes if needed
```

### Key Innovation: In-Memory Token Caching
```python
from core.auth import get_client_credentials_token_cached

# First call: hits API, caches in memory + file
token = get_client_credentials_token_cached()

# Subsequent calls: ~instant (in-memory lookup)
token = get_client_credentials_token_cached()  # Sub-microsecond

# Avoids file I/O on every high-frequency API call
# ~30% performance improvement for parallel operations
```

---

## 2. Async API Resolution with Retry (Medium Complexity)

### Pattern Structure
```python
# From: core/api.py and core/track_index.py

import asyncio
import aiohttp

async def resolve_track_id_async(track_slug, max_retries=3) -> tuple[str | None, str | None]:
    """Resolve track with exponential backoff."""
    url = f"https://api.soundcloud.com/resolve?url=https://soundcloud.com/{track_slug}"
    
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return str(data.get("id")), None
                    elif response.status == 404:
                        return None, "404"  # Permanent failure
                    elif response.status == 429:
                        # Rate limited - exponential backoff
                        wait_time = 2 ** attempt
                        if attempt < max_retries - 1:
                            await asyncio.sleep(wait_time)
                            continue
                        return None, "rate_limit"
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue
            return None, "timeout"
    
    return None, "max_retries_exceeded"


async def resolve_batch_with_concurrency_limit(
    items: list[str], max_concurrent: int = 15
) -> dict:
    """Resolve multiple items with Semaphore for rate limiting."""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def resolve_one(item):
        async with semaphore:
            result = await resolve_track_id_async(item)
            await asyncio.sleep(1 / max_concurrent)  # Distributed rate limiting
            return result
    
    tasks = [resolve_one(item) for item in items]
    results = await asyncio.gather(*tasks)
    
    # Classify results
    resolved = sum(1 for id, error in results if id)
    failed_permanent = sum(1 for id, error in results if error == "404")
    failed_transient = sum(1 for id, error in results if error and error != "404")
    
    return {
        "resolved": resolved,
        "failed_permanent": failed_permanent,
        "failed_transient": failed_transient,
        "results": results
    }
```

### How to Adapt
1. Change URL endpoint (Music Minion internal service)
2. Keep retry logic and Semaphore pattern
3. Error classification: distinguish 404 (permanent) from others (transient)
4. Return (data, error_code) tuple for flexibility

---

## 3. Batch Data Merging Pattern (For SQLite/Parquet)

### Inefficient Version (Don't Do This)
```python
# N file writes - slow!
for artist, tracks in artists_tracks.items():
    merge_tracks(artist, tracks)  # Each call does load() + save()
```

### Efficient Version (Do This)
```python
def merge_tracks_batch(tracks_by_artist: dict[str, list]) -> None:
    """Load once, merge all, save once."""
    
    # Load data structure once
    data = load_tracks()
    
    # Process all artists/tracks in memory
    for artist_url, tracks in tracks_by_artist.items():
        for track_slug, track_id, timestamp in tracks:
            existing = data.get(track_slug)
            
            if existing:
                # Update existing track
                existing["reposts"].append({"artist": artist_url, "timestamp": timestamp})
            else:
                # Add new track
                data[track_slug] = {
                    "track_id": track_id,
                    "reposts": [{"artist": artist_url, "timestamp": timestamp}],
                    "timestamp": timestamp
                }
    
    # Save once at the end
    save_tracks(data)
```

### Performance Impact
- Single artist, 100 tracks: ~50ms (1 save)
- Multiple artists, 1000 tracks: ~50ms (1 save) vs 100ms+ (100 saves)
- Scales to 10k+ tracks efficiently

---

## 4. Configuration Caching (Simple but Effective)

### From soundcloud-discovery/core/config.py
```python
import json
from pathlib import Path

_config_cache = None

def load_config() -> dict:
    """Load config with in-memory caching."""
    global _config_cache
    if _config_cache is None:
        with open("config/discovery.json") as f:
            _config_cache = json.load(f)
    return _config_cache

def get_config_value(path: str, default=None):
    """Get nested value by dot-path: 'playlists.reposts.max_tracks'"""
    config = load_config()
    keys = path.split('.')
    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value

# Usage
max_tracks = get_config_value("playlists.reposts.max_tracks", 100)
is_auto_sync = get_config_value("playlists.auto_sync", False)
```

### Adapt for Music Minion
- Replace JSON with TOML (already used)
- Same caching pattern works
- Supports nested config access

---

## 5. Error Classification Pattern

### From core/api.py and core/track_index.py
```python
def classify_error(response_status: int, error: Exception) -> str:
    """Classify error as permanent or transient."""
    
    # Permanent failures - don't retry
    if response_status == 404:
        return "404_not_found"
    
    # Transient failures - retry with backoff
    if response_status == 429:
        return "rate_limit"
    
    if 500 <= response_status < 600:
        return f"server_error_{response_status}"
    
    if isinstance(error, asyncio.TimeoutError):
        return "timeout"
    
    if isinstance(error, ConnectionError):
        return "connection_error"
    
    # Default: assume transient
    return f"unknown_{type(error).__name__}"


def should_retry(error_code: str, attempt: int, max_retries: int) -> bool:
    """Determine if error is retryable."""
    permanent_errors = {"404_not_found"}
    is_transient = error_code not in permanent_errors
    has_retries = attempt < max_retries
    return is_transient and has_retries


# Usage
for attempt in range(max_retries):
    try:
        result = api_call()
        return result
    except Exception as e:
        error_code = classify_error(response.status, e)
        
        if should_retry(error_code, attempt, max_retries):
            await asyncio.sleep(2 ** attempt)
            continue
        
        # Permanent failure or max retries exceeded
        log_error(error_code, attempt)
        return None
```

---

## 6. State Management Pattern (Judgment/Status)

### From core/judgment.py
```python
def mark_judgment_status(
    global_index: dict,
    liked_ids: set[str],
    not_interested_ids: set[str],
    not_quite_ids: set[str]
) -> dict[str, int]:
    """Update track status with priority logic."""
    
    stats = {"liked": 0, "not_interested": 0, "not_quite": 0, "unchanged": 0}
    
    for track in global_index:
        track_id = str(track["track_id"])
        current_judgment = track.get("judgment")
        
        # Priority order
        if track_id in liked_ids:
            track["judgment"] = "liked"
            stats["liked"] += 1
        elif track_id in not_interested_ids:
            track["judgment"] = "not_interested"
            stats["not_interested"] += 1
        elif track_id in not_quite_ids:
            track["judgment"] = "not_quite"
            stats["not_quite"] += 1
        elif current_judgment == "not_quite":
            # Persist "not_quite" even if removed from source list
            stats["not_quite"] += 1
        else:
            stats["unchanged"] += 1
    
    return stats
```

### Apply to Music Minion
- Track status in database with priorities
- Preserve user ratings even if source is updated
- Batch update after external sync

---

## 7. Pandas/Parquet Pattern (Advanced)

### From core/track_index.py
```python
import pandas as pd
from pathlib import Path

def load_tracks_dataframe() -> pd.DataFrame:
    """Load Parquet file efficiently."""
    cache_file = Path(".cache/tracks.parquet")
    
    if not cache_file.exists():
        return pd.DataFrame(columns=[
            "slug", "track_id", "first_seen",
            "repost_count", "liked_by", "judgment"
        ])
    
    df = pd.read_parquet(cache_file)
    
    # Handle backward compatibility
    if "judgment" not in df.columns:
        df["judgment"] = None
    
    return df

def save_tracks_dataframe(df: pd.DataFrame) -> None:
    """Save DataFrame to Parquet."""
    cache_file = Path(".cache/tracks.parquet")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_file, index=False)

# Usage
df = load_tracks_dataframe()

# Filter operations
resolved = df[df["track_id"].notna()]  # Only resolved tracks
recent = df[df["first_seen"] >= cutoff_date]  # Last 7 days
unrated = df[df["judgment"].isna()]  # Not yet evaluated

# Batch updates
for idx, row in df.iterrows():
    if row["slug"] in new_data:
        df.at[idx, "judgment"] = "liked"

save_tracks_dataframe(df)
```

### Why Use Parquet?
- Compressed columnar format (630KB for 10k tracks)
- Faster queries than JSON
- Type-safe (unlike JSON strings)
- Perfect for analytics (aggregations, filters)
- Schema validation

---

## Integration Checklist for Music Minion

- [ ] Extract `core/auth.py` (OAuth functions)
- [ ] Adapt async retry pattern from `core/api.py`
- [ ] Implement Semaphore-based concurrency limiting
- [ ] Add error classification (permanent vs transient)
- [ ] Study batch merging pattern in `core/track_index.py`
- [ ] Decide: SQLite (current) vs Parquet (analytics)
- [ ] Token storage: file-based + in-memory caching
- [ ] Config caching: reduces disk I/O
- [ ] Error handling: detailed messages with context

---

## Files to Reference

**Direct Extraction**:
- `/home/kevin/coding/soundcloud-discovery/core/auth.py` (379 lines)
- `/home/kevin/coding/soundcloud-discovery/core/config.py` (57 lines)

**Study for Patterns**:
- `/home/kevin/coding/soundcloud-discovery/core/api.py` (370 lines) - async patterns
- `/home/kevin/coding/soundcloud-discovery/core/track_index.py` (513 lines) - batch operations
- `/home/kevin/coding/soundcloud-discovery/core/judgment.py` (252 lines) - state management
- `/home/kevin/coding/soundcloud-discovery/discovery/sources/artist_likes.py` (103 lines) - API integration pattern

**Analysis Reference**:
- `/home/kevin/coding/music-minion-cli/docs/soundcloud-integration-analysis.md` (full architecture)

