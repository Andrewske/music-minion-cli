# SoundCloud Discovery Codebase Analysis

## Architecture Overview

The soundcloud-discovery project is a well-architected system for EDM artist discovery and track curation. It uses a **three-layer architecture**:

1. **Core Layer** (`core/`): Infrastructure and API access
2. **Domain Layer** (`discovery/` + `likes/`): Business logic
3. **CLI Layer** (`cli/`): User-facing commands

### Key Design Patterns
- **Pure Functions**: Core modules use functional programming (no classes except data containers)
- **Modular Sources**: Discovery sources abstracted via Protocol (typing-only, zero runtime overhead)
- **Parquet-based Storage**: High-performance analytics using Pandas + Arrow
- **Token Caching**: Both file-based and in-memory token caching for performance

---

## 1. Authentication Implementation

### OAuth 2.0 Flows (`core/auth.py`)

**Two distinct flows**:

#### A. Authorization Code + PKCE (User Actions)
```python
# For playlists, likes - requires user interaction
generate_pkce() -> {"code_verifier": str, "code_challenge": str}
generate_state() -> str
build_auth_url(client_id, redirect_uri, code_challenge, state) -> str
exchange_code_for_token(code, client_id, client_secret, redirect_uri, code_verifier) -> TokenData
refresh_access_token(refresh_token, client_id, client_secret) -> TokenData
```

**Token Storage** (`.env.soundcloud_tokens`):
```json
{
  "access_token": "jwt_token",
  "refresh_token": "refresh_token",
  "expires_at": "ISO8601 timestamp",
  "scope": ""
}
```

**Auto-refresh Logic** (`core/api.py:get_oauth_token()`):
- Loads from `.env.soundcloud_tokens` file
- Checks expiry (5-minute buffer)
- Auto-refreshes if expired using refresh_token
- Falls back to `.env SOUNDCLOUD_OAUTH_TOKEN` for backward compatibility

#### B. Client Credentials (Public Resources)
```python
# For public data (likes, track resolution)
get_client_credentials_token(force_refresh=False) -> str
get_client_credentials_token_cached(force_refresh=False) -> str
```

**Token Storage** (`.env.soundcloud_app_token`):
```json
{
  "access_token": "app_access_token",
  "expires_at": "ISO8601 timestamp",
  "token_type": "Bearer"
}
```

**Caching Strategy**:
- File-based cache in `.env.soundcloud_app_token`
- In-memory cache in module-level dict `_token_cache`
- 5-minute buffer before expiry
- Cached tokens avoid repeated file I/O on high-frequency calls

**Key Innovation**: `get_client_credentials_token_cached()` provides 30%+ performance improvement for parallel operations by using in-memory caching.

---

## 2. API Client Code (`core/api.py`)

### Token Management
```python
get_client_id() -> str              # From .env
get_client_secret() -> str          # From .env
get_oauth_token() -> str            # User OAuth (auto-refresh)
```

### Track Resolution
```python
# Synchronous
resolve_track_id(track_slug: str) -> str | None
    # "artist/track-name" -> "123456"
    # Uses Client Credentials
    # Endpoint: GET /resolve?url=https://soundcloud.com/{slug}

# Asynchronous with Retry Logic
resolve_track_id_async(track_slug, max_retries=3) -> (id, error_code)
    # Returns tuple: (track_id, error_code)
    # error_code: "404" (deleted), "timeout", "rate_limit", "server_error_XXX"
    # Retry strategy:
    #   - 404: permanent failure, don't retry
    #   - 429: rate limited, exponential backoff (2^attempt seconds)
    #   - 5xx: server error, 1 second backoff
    #   - timeout: 1 second backoff
```

### User Resolution
```python
resolve_user_id(user_url: str) -> str | None
    # "https://soundcloud.com/artist" -> "123456"
    # Endpoint: GET /resolve?url={user_url}
```

### Playlist Operations
```python
# Fetch playlist (read)
fetch_playlist(playlist_id: str) -> dict | None
    # Endpoint: GET /playlists/{id}
    # Returns full playlist object

# Update playlist (write)
update_playlist(playlist_id, track_ids, oauth_token=None) -> None
    # Endpoint: PUT /playlists/{id}
    # Full replacement of tracks
    # Payload format:
    #   {"playlist": {"tracks": [{"urn": "soundcloud:tracks:123"}, ...]}}
    # Errors raise RuntimeError with response details
```

### User Likes (Pagination)
```python
fetch_user_likes(user_id, limit=50, next_href=None) -> (tracks, next_href)
    # Endpoint: GET /users/soundcloud:users:{id}/likes/tracks
    # Pagination: linked_partitioning with cursor
    # Returns (collection, next_href for cursor-based pagination)
```

### Error Handling
- HTTP errors: `raise_for_status()` propagates exceptions
- Network errors: Caught as `requests.HTTPError`, `aiohttp.ClientError`
- Async retry logic with exponential backoff for transient errors
- 404 treated as permanent failure (track deleted)

---

## 3. Data Models

### Track Data Structures

**From API Response** (discovery/sources/artist_likes.py):
```python
track = {
    "id": str,
    "permalink_url": "https://soundcloud.com/artist/track",
    "created_at": "2025/10/17 04:35:05 +0000",
    "kind": "track"
}
```

**Stored in Global Index** (Parquet DataFrame):
```python
{
    "slug": "artist/track-name",
    "track_id": "123456" or None,
    "first_seen": datetime,
    "repost_count": int,
    "reposted_by": [{"artist": "url", "timestamp": "ISO8601"}, ...],
    "like_count": int,
    "liked_by": [{"artist": "url", "timestamp": "ISO8601"}, ...],
    "judgment": "liked" | "not_interested" | "not_quite" | None,
    "resolution_status": "deleted" | "failed_transient" | None
}
```

**Internal Processing** (discovery/sources/artist_likes.py:parse_track_data):
```python
(track_slug: str, liked_at: datetime)  # From API response parsing
```

### Playlist Models
```python
{
    "id": str,
    "title": str,
    "tracks": [track_objects],
    # ... other fields
}
```

---

## 4. Rate Limiting & Error Handling

### Rate Limiting Strategies

**1. Async Resolution with Semaphore** (core/track_index.py):
```python
async def resolve_missing_track_ids_async(
    df, recent_hours=None, max_concurrent=15, log_errors=False
):
    semaphore = asyncio.Semaphore(max_concurrent)
    # Distributed rate limiting: 1/(max_concurrent) per request
    # ~15 req/sec across 15 concurrent requests
    # Returns detailed stats: resolved, failed_permanent, failed_transient
```

**2. Sync Resolution with Sleep** (core/track_index.py):
```python
def resolve_missing_track_ids(max_tracks=None, recent_hours=None):
    # 1 request per second to avoid API blocks
    time.sleep(1)
```

**3. Batch Operations** (discovery/artist_cache.py):
- Configurable batch_size (default: 15)
- batch_delay_seconds (default: 1.5)
- Incremental updates with stop_at_known optimization

### Error Classification (resolve_track_id_async)
```python
# Permanent failures (don't retry):
"404"  # Track deleted

# Transient failures (retry with backoff):
"timeout"              # Network timeout
"rate_limit"           # HTTP 429
"server_error_XXX"     # HTTP 5xx
"client_error_NAME"    # aiohttp client errors
"max_retries_exceeded" # Hit retry limit

# Detailed error logging:
error_details = [
    {"slug": "artist/track", "error_type": "permanent|transient", 
     "error_code": "404|timeout|..."}
]
```

---

## 5. Caching Strategy

### Parquet-based Data Lake (High-Performance)
- **Location**: `.cache/global_tracks.parquet`
- **Size**: ~630KB for 10k tracks
- **Format**: Apache Arrow/Parquet (columnar, compressed)
- **Usage**: Global track index with repost/like provenance

### JSON Caches (Operational Metadata)
- **`.cache/sync_state.json`**: Unified sync timestamps
  ```json
  {
    "likes": {"last_sync": "ISO8601", "total_likes": 6429},
    "playlist": {"playlist_id": "...", "last_synced": "...", "current_tracks": [...]}
  }
  ```

- **`.cache/discovery/reposts_cache.json`**: Scraping metadata
- **`.cache/discovery/artist_likes_cache.json`**: API fetch metadata
  ```json
  {
    "artist_url": {
      "last_check": "ISO8601",
      "last_activity_time": "ISO8601",
      "current_check_interval_hours": int,
      "total_tracks": int,
      "activity_count": int
    }
  }
  ```

### Token Caching
- **File-based**: `.env.soundcloud_tokens`, `.env.soundcloud_app_token`
- **In-memory**: Module-level `_token_cache` dict
  ```python
  _token_cache: dict[str, tuple[str, float]] = {}  # {cache_key: (token, expiry_timestamp)}
  ```

### Batch Merging Pattern (core/track_index.py)
```python
# Efficient: Load/save Parquet once
merge_tracks_batch(tracks_by_artist, source="like")
    # Single save operation vs. N saves for individual merges
```

### Configuration Caching (core/config.py)
```python
_config_cache = None  # Cached JSON config from config/discovery.json
load_config()         # Uses cache if loaded
reload_config()       # Force disk reload
get_config_value(path, default)  # Dot-path access: "playlists.reposts.max_tracks"
```

---

## 6. Reusable Components for Music Minion

### Extract These Functions

#### 1. **OAuth & Token Management** (Reusable)
```python
from core.auth import (
    generate_pkce,
    generate_state,
    build_auth_url,
    exchange_code_for_token,
    refresh_access_token,
    save_tokens,
    load_tokens,
    is_token_expired,
    get_client_credentials_token_cached,  # Most valuable
)
```

**Why valuable**: 
- Handles PKCE properly
- Implements auto-refresh with 5-min buffer
- In-memory caching avoids file I/O
- Ready for use with any OAuth 2.0 service

#### 2. **Async Resolution with Retry** (Reusable)
```python
from core.api import resolve_track_id_async

# Provides:
# - Exponential backoff
# - Transient error classification
# - Concurrent request limiting with Semaphore
# - Error logging/reporting
```

**Why valuable**:
- Can adapt endpoint for any resolver service
- Handles rate limiting gracefully
- Returns error classification for analytics

#### 3. **Parquet-based Track Index** (Reusable Pattern)
```python
from core.track_index import (
    load_global_tracks,
    save_global_tracks,
    merge_tracks,
    merge_tracks_batch,
    resolve_missing_track_ids_async,
)
```

**Why valuable**:
- Efficient bulk operations
- Batch merging (single save)
- Async resolution pattern
- Timestamp tracking for incremental syncs

#### 4. **Configuration Management** (Reusable)
```python
from core.config import (
    load_config,
    reload_config,
    get_config_value,  # Dot-path access is nice
)
```

**Why valuable**:
- Caching reduces repeated disk I/O
- Dot-path nested access (`"playlists.reposts.max_tracks"`)
- Works with any JSON config

#### 5. **Judgment/State Management** (Reusable Pattern)
```python
from core.judgment import (
    fetch_not_interested_tracks,  # Pattern for fetching curated lists
    mark_judgment_status,          # Pattern for batch status updates
)
```

### Integration Opportunities for Music Minion

**SoundCloud as a "Service"** (Discovery Source):
```python
# Similar to reposts/artist_likes sources
def fetch_soundcloud_likes(user_id) -> list[tuple[str, datetime]]:
    """Fetch your SoundCloud likes for Music Minion library."""
    # Use fetch_user_likes + resolve_track_id_async pattern
    # Merge into Music Minion's track database
```

**Playlist Sync Pattern**:
```python
# Update Music Minion playlists based on SoundCloud curation
update_playlist(playlist_id, track_ids)
# Already works with Music Minion's database structure
```

---

## 7. Code Quality Observations

### Strengths
- **Type hints everywhere**: All functions have return types
- **Pure functions**: Minimal side effects (except file I/O)
- **Error messages**: Detailed with context (response codes, URLs)
- **Async/await**: Proper concurrent handling with Semaphore
- **Backward compatibility**: Handles .env fallbacks
- **Comprehensive docstrings**: Clear Args/Returns sections
- **Configuration as code**: JSON config not hardcoded

### Patterns to Adopt
1. **Token caching layers**: File + in-memory for both correctness and performance
2. **Exponential backoff**: For transient API errors
3. **Batch operations**: Single load/save for Parquet (avoid N-write bottleneck)
4. **Protocol for abstraction**: Typing-only (zero overhead)
5. **Error classification**: Distinguish permanent vs. transient failures

---

## 8. Dependency Stack

```toml
requests>=2.32.0           # HTTP client (sync)
aiohttp>=3.9.0            # HTTP client (async)
pandas>=2.0.0             # Data manipulation
pyarrow>=14.0.0           # Parquet format
python-dotenv>=1.0.0      # .env loading
playwright>=1.40.0        # Web scraping (for reposts)
```

**For Music Minion Integration**:
- Use `requests` (already a dependency)
- Can add `aiohttp` for high-concurrency scenarios
- Consider Parquet for large track libraries (Music Minion already uses SQLite, but Parquet great for analytics)

---

## 9. Configuration Structure

**Key Decisions**:
- Config file: `config/discovery.json` (JSON, not TOML)
- Tokens: Plain JSON files (could be encrypted with GPG, see `.env.soundcloud_tokens.gpg`)
- Artists list: `config/artists.txt` (plain text, one per line)
- Caches: `.cache/` directory with subdirectories

**Recommended for Music Minion**:
- Keep using TOML for configuration (already established)
- Token storage: Consider using `keyring` library or encryption at rest
- Cache directory: Can follow same pattern (`.cache/soundcloud/` subdirectory)

---

## Summary: What to Extract

| Component | Location | Effort | Value |
|-----------|----------|--------|-------|
| PKCE OAuth flow | `core/auth.py` | Low | High - ready for any service |
| Token caching pattern | `core/auth.py` | Low | High - saves file I/O |
| Async retry logic | `core/api.py` | Medium | High - rate limit handling |
| Parquet merge pattern | `core/track_index.py` | Medium | High - bulk operations |
| Config loader | `core/config.py` | Low | Medium - nice for complex config |
| Resolution with Semaphore | `core/track_index.py` | Medium | Medium - concurrent limiting |

**Start Here**: 
1. Extract `core/auth.py` functions (pure, self-contained)
2. Study async pattern in `core/api.py:resolve_track_id_async()`
3. Understand Parquet merge pattern in `core/track_index.py`
4. Consider Parquet for Music Minion's large library analytics

