# SoundCloud Discovery Integration Analysis

Complete analysis of the soundcloud-discovery codebase for potential integration with Music Minion CLI.

## Documents

### 1. [soundcloud-integration-analysis.md](./soundcloud-integration-analysis.md)
**Full Architecture Reference (462 lines, 14KB)**

Comprehensive guide covering:
- Architecture overview (3-layer design)
- OAuth 2.0 authentication flows (PKCE + Client Credentials)
- API client implementation (track resolution, playlists, user likes)
- Data models and structures
- Rate limiting strategies (Semaphore pattern)
- Caching architecture (Parquet, JSON, tokens)
- Error handling and classification
- Reusable components ranked by effort/value
- Code quality observations
- Dependency analysis

**Best for**: Understanding overall architecture, identifying reusable patterns, detailed API reference

### 2. [soundcloud-reusable-code.md](./soundcloud-reusable-code.md)
**Quick Reference with Code Snippets (385 lines, 12KB)**

Practical guide with copy-paste ready code:
1. OAuth token management
2. Async API resolution with exponential backoff
3. Batch data merging pattern
4. Configuration caching
5. Error classification
6. State management patterns
7. Pandas/Parquet examples
8. Integration checklist

**Best for**: Implementing specific features, copy-pasting patterns, quick lookup

## Quick Start

### For Immediate Extraction
Start with these self-contained, low-effort components:

1. **OAuth Token Management** (core/auth.py)
   - PKCE generation
   - Token exchange
   - Auto-refresh logic
   - File + in-memory caching
   - Ready to use with any OAuth 2.0 service

2. **Error Classification** (from core/api.py)
   - Permanent vs transient errors
   - Exponential backoff logic
   - Applicable to any API

3. **Config Caching** (core/config.py)
   - Dot-path access to nested config
   - In-memory caching reduces disk I/O

### For Integration Planning
Study these patterns before implementation:

1. **Async Resolution with Retry**
   - Semaphore-based rate limiting
   - Handles 404, timeout, 429, 5xx errors
   - Returns (data, error_code) tuples

2. **Batch Merging Pattern**
   - Single load/save vs N operations
   - Massive I/O reduction for bulk operations

3. **Parquet Storage**
   - Columnar format for analytics
   - 630KB for 10k tracks (compressed)
   - Better than JSON for large datasets

## Key Insights

### Authentication
- Two flows: Authorization Code (user) + Client Credentials (public)
- Smart token caching: File-based (persistence) + in-memory (performance)
- Auto-refresh with 5-minute buffer
- 30% performance improvement from in-memory caching

### API Design
- Pure functions, no OOP overhead
- Comprehensive error classification
- Async/await for concurrent operations
- Rate limiting via Semaphore (distributed)
- Exponential backoff for transient errors

### Data Management
- Parquet for analytics (columnar, compressed)
- JSON for metadata and sync state
- Batch operations minimize I/O
- Track provenance (who reposted/liked)

### Performance
- Token caching: module-level dict avoids file I/O
- Config caching: reduces repeated disk reads
- Batch merging: 50ms for 1000 tracks vs 100ms+ per individual
- Async resolution: 15 concurrent requests = ~15 req/sec

## Integration Roadmap

### Phase 1: OAuth Integration
Extract from `core/auth.py`:
- Generate PKCE parameters
- Build authorization URL
- Exchange code for token
- Auto-refresh token

### Phase 2: API Client
Adapt from `core/api.py`:
- Async resolution pattern
- Exponential backoff retry
- Semaphore-based rate limiting
- Error classification

### Phase 3: Data Integration
Learn from `core/track_index.py`:
- Batch merging pattern
- Parquet storage (optional)
- State synchronization

### Phase 4: Service Integration
Follow `discovery/sources/artist_likes.py`:
- API pagination pattern
- Track parsing and transformation
- Incremental updates (stop_at_known)

## File Locations

### Source Code
- `/home/kevin/coding/soundcloud-discovery/core/auth.py` - OAuth (379 lines)
- `/home/kevin/coding/soundcloud-discovery/core/api.py` - API client (370 lines)
- `/home/kevin/coding/soundcloud-discovery/core/config.py` - Config (57 lines)
- `/home/kevin/coding/soundcloud-discovery/core/track_index.py` - Batch ops (513 lines)
- `/home/kevin/coding/soundcloud-discovery/core/judgment.py` - State (252 lines)
- `/home/kevin/coding/soundcloud-discovery/discovery/sources/artist_likes.py` - Pattern (103 lines)

### Analysis Documents
- `/home/kevin/coding/music-minion-cli/docs/soundcloud-integration-analysis.md`
- `/home/kevin/coding/music-minion-cli/docs/soundcloud-reusable-code.md`

## Extraction Priority

### High Value, Low Effort
- [ ] OAuth token functions (pure, self-contained)
- [ ] Config caching pattern (57 lines)
- [ ] Error classification (10-20 lines)

### High Value, Medium Effort
- [ ] Async retry logic (copy-paste ready in docs)
- [ ] Batch merging (50-100 lines adapted)
- [ ] Semaphore rate limiting (20 lines)

### Optional (Advanced)
- [ ] Parquet integration (if analytics needed)
- [ ] Playwright scraping (for reposts tracking)
- [ ] LLM prompt optimization (advanced feature)

## Architecture Comparison

### soundcloud-discovery
- **Storage**: Parquet + JSON
- **HTTP**: requests + aiohttp
- **Config**: JSON with caching
- **Auth**: OAuth 2.0 (PKCE + Client Credentials)
- **Rate Limiting**: Semaphore + exponential backoff

### Music Minion
- **Storage**: SQLite + TOML
- **HTTP**: requests (aiohttp not used)
- **Config**: TOML loaded at startup
- **Auth**: None (local library)
- **Rate Limiting**: None (local library)

### Bridging the Gap
1. Keep Music Minion's SQLite (no Parquet needed)
2. Use OAuth pattern for SoundCloud integration
3. Adapt async retry for API calls
4. Keep TOML config (change JSON to TOML parsing in extracted code)

## Questions & Decisions

**Q: Should Music Minion integrate with SoundCloud?**
- A: Optional feature - adds discovery capability without changing core functionality

**Q: Extract core/auth.py as-is or adapt?**
- A: Extract as-is (pure functions), wrap with Music Minion credentials storage

**Q: Use Parquet or stay with SQLite?**
- A: Stay with SQLite for simplicity. Parquet useful if building analytics features later.

**Q: Include aiohttp dependency?**
- A: Optional. Only needed if implementing high-concurrency async resolution.

**Q: Token storage strategy?**
- A: Recommend keyring library for better security than plaintext .env files

## Next Steps

1. Read `soundcloud-integration-analysis.md` for context
2. Review code snippets in `soundcloud-reusable-code.md`
3. Decide which features to integrate with Music Minion
4. Extract and adapt code following the priority order
5. Add comprehensive tests for OAuth and API integration

## References

- SoundCloud API Documentation: https://soundcloud.com/api
- OAuth 2.0 PKCE Spec: https://tools.ietf.org/html/rfc7636
- asyncio Semaphore: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore
- Parquet Format: https://parquet.apache.org/

---

**Analysis Date**: November 18, 2025  
**Codebase Size**: 4997 Python files, ~4.8MB  
**Focus**: Core infrastructure (auth, API, data management)  
**Effort Estimate**: 2-4 weeks for full integration, 1-2 weeks for basic auth + API
