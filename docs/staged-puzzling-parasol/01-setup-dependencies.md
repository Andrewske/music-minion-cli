---
task: 01-setup-dependencies
status: done
depends: []
files: []
---

# Setup Dependencies

## Context
Verify the OpenAI Python SDK is available. It's already in pyproject.toml (line 13).

## Files to Modify/Create
None - dependency already exists.

## Implementation Details
The user will need to add `OPENAI_API_KEY` to their `.env` file (not tracked in git).

## Verification
```bash
uv run python -c "import openai; print('OpenAI SDK installed:', openai.__version__)"
```

Expected: OpenAI SDK version printed without errors.
