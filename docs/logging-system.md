# Logging System Architecture

## Overview
A dual-logging system using **loguru** that separates background/debug logs from user-facing messages, with special handling for terminal UI (blessed) integration.

## Key Components

### 1. Loguru Setup (`core/output.py`)
```python
from loguru import logger
from pathlib import Path

def setup_loguru(log_file: Path, level: str = "INFO") -> None:
    logger.remove()  # Remove default handler
    logger.add(
        log_file,
        rotation="10 MB",
        retention=5,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} | {message}",
        enqueue=False,  # Synchronous, thread-safe
    )
```

### 2. Dual Logging Pattern

**Direct loguru** - for background/internal operations:
```python
from loguru import logger
logger.info("Starting sync...")
logger.exception("Failed")  # Auto-includes stack trace in except blocks
```

**`log()` helper** - for user-facing messages (writes to file + UI):
```python
def log(message: str, level: str = "info") -> None:
    # Always log to file
    log_func = getattr(logger, level)
    log_func(message)

    # Route to UI if in blessed mode and not suppressed
    with _blessed_mode_lock:
        if _blessed_mode_active:
            silent = getattr(threading.current_thread(), "silent_logging", False)
            if not silent:
                with _pending_messages_lock:
                    _pending_history_messages.append((message, color))
```

### 3. Background Thread Pattern
Suppress stdout while preserving file logging:
```python
def _background_worker():
    threading.current_thread().silent_logging = True
    try:
        logger.info("Working...")  # Goes to file only
    except Exception:
        logger.exception("Failed")  # Stack trace to file
    finally:
        threading.current_thread().silent_logging = False
```

### 4. Message Queue (Race Condition Fix)
Prevents UI state overwrites when commands call `log()`:
```python
# Global state
_pending_history_messages: list[tuple[str, str]] = []
_pending_messages_lock = threading.Lock()

def drain_pending_history_messages() -> list[tuple[str, str]]:
    with _pending_messages_lock:
        messages = _pending_history_messages.copy()
        _pending_history_messages.clear()
        return messages
```

In command executor:
```python
ctx, result = handle_command(ctx, cmd, args)
# Drain queued messages after command completes
for msg, color in drain_pending_history_messages():
    ui_state = add_history_line(ui_state, msg, color)
```

## Configuration (`core/config.py`)
```python
@dataclass
class LoggingConfig:
    level: str = "INFO"
    log_file: Optional[str] = None  # Default: ~/.local/share/app/app.log
    max_file_size_mb: int = 10
    backup_count: int = 5
```

## Key Rules
1. **Never use `print()`** - breaks terminal UI, no rotation
2. **Use `logger.exception()` in except blocks** - auto stack traces
3. **Set `silent_logging = True` in background threads** - suppresses UI output
4. **Always cleanup in `finally`** - reset `silent_logging = False`
5. **Catch specific exceptions** - never bare except

## Log Output Format
```
2025-11-25 21:08:23 | INFO     | module.name:42 | Message here
```
