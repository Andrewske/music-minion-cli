# Add --web Flag to CLI Parser

## Files to Modify
- `src/music_minion/cli.py` (modify)

## Implementation Details

Add a new `--web` flag to the argument parser that enables web UI mode.

### Changes Required

#### 1. Add --web argument to parser (around line 140)

**Location:** After the `--dev` flag definition

```python
parser.add_argument(
    "--web",
    action="store_true",
    help="Enable web UI (starts backend + frontend dev servers)",
)
```

#### 2. Set environment variable when flag is present (around line 223)

**Location:** After dev mode environment variable handling

```python
# After the dev mode handling:
if args.web:
    os.environ["MUSIC_MINION_WEB_MODE"] = "1"
```

## Context

**Existing pattern:**
The CLI already uses environment variables to pass flags to the main interactive mode:
- `--dev` → `MUSIC_MINION_DEV_MODE=1`

**Why environment variable:**
- The `cli.py` module handles argument parsing
- The `main.py` module runs the interactive mode
- Environment variables are the established communication method between these modules

## Acceptance Criteria

✅ `--web` flag appears in help text (`music-minion --help`)
✅ Help text clearly describes what the flag does
✅ Environment variable `MUSIC_MINION_WEB_MODE` is set to "1" when flag is present
✅ Flag can be combined with other flags (e.g., `--dev --web`)
✅ No breaking changes to existing argument parsing

## Dependencies
- Task 01 (web_launcher module) must exist before testing, but not for this code change
