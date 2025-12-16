# Move Backend Logs to Project Root

## Files to Modify/Create
- src/music_minion/web_launcher.py
- src/music_minion/main.py
- CLAUDE.md

## Implementation Details
Backend logs are currently saved to /tmp which makes them hard to access. Move them to project root for easier debugging.

1. Update log paths in web_launcher.py to use PROJECT_ROOT
2. Update user message in main.py
3. Update CLAUDE.md documentation
4. Test that logs are created in correct location

## Acceptance Criteria
- Logs save to project root
- Documentation updated
- Web mode works
- Follow CLAUDE.md FP + type-safety rules

## Dependencies
None