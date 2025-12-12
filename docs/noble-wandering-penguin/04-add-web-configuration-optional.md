# Add Web Configuration (Optional Enhancement)

## Files to Modify
- `src/music_minion/core/config.py` (modify)
- `src/music_minion/web_launcher.py` (modify)

## Implementation Details

Add configurable web settings to allow users to customize ports and reload behavior. This is an **optional enhancement** - the core functionality works without it.

### Changes to config.py

#### 1. Add WebConfig dataclass

```python
@dataclass
class WebConfig:
    """Configuration for web UI mode."""
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_port: int = 5173
    auto_reload: bool = True  # For uvicorn --reload flag
```

#### 2. Add web field to Config dataclass

```python
@dataclass
class Config:
    # ... existing fields ...
    web: WebConfig = field(default_factory=WebConfig)
```

### Changes to web_launcher.py

#### 1. Accept optional config parameter

Update function signatures to accept optional config:

```python
def check_web_prerequisites(config: Optional['WebConfig'] = None) -> tuple[bool, str]:
    """Check prerequisites with optional config for custom ports."""
    backend_port = config.backend_port if config else 8000
    frontend_port = config.frontend_port if config else 5173

    # Check ports with config values
    if not is_port_available(backend_port):
        return False, f"Port {backend_port} already in use (FastAPI backend)"
    if not is_port_available(frontend_port):
        return False, f"Port {frontend_port} already in use (Vite frontend)"

    # ... rest of checks ...
```

#### 2. Use config values in process startup

```python
def start_uvicorn_process(config: Optional['WebConfig'] = None) -> subprocess.Popen:
    """Start uvicorn with optional config."""
    host = config.backend_host if config else "0.0.0.0"
    port = config.backend_port if config else 8000
    reload_flag = "--reload" if (config.auto_reload if config else True) else ""

    command = [
        "uv", "run", "uvicorn", "web.backend.main:app",
        "--host", host,
        "--port", str(port),
    ]
    if reload_flag:
        command.append(reload_flag)

    # ... rest of implementation ...
```

```python
def start_vite_process(config: Optional['WebConfig'] = None) -> subprocess.Popen:
    """Start Vite with optional config for port."""
    port = config.frontend_port if config else 5173

    command = ["npm", "run", "dev", "--", "--host", "--port", str(port)]

    # ... rest of implementation ...
```

### Changes to main.py

Update the web launcher calls to pass config:

```python
if web_mode:
    from . import web_launcher

    # Pre-flight checks with config
    success, error = web_launcher.check_web_prerequisites(current_config.web)
    if not success:
        safe_print(f"❌ Cannot start web mode: {error}", style="red")
        sys.exit(1)

    # Start web processes with config
    safe_print("🌐 Starting web services...", style="cyan")
    uvicorn_proc = web_launcher.start_uvicorn_process(current_config.web)
    vite_proc = web_launcher.start_vite_process(current_config.web)
    web_processes = (uvicorn_proc, vite_proc)

    # Print URLs with actual config values
    safe_print(f"   Backend:  http://{current_config.web.backend_host}:{current_config.web.backend_port}", style="green")
    safe_print(f"   Frontend: http://localhost:{current_config.web.frontend_port}", style="green")
    safe_print("   Logs: /tmp/music-minion-{uvicorn,vite}.log", style="dim")
```

## Configuration File Example

Users can customize settings in their config file:

```toml
[web]
backend_host = "127.0.0.1"  # Localhost only instead of 0.0.0.0
backend_port = 8080         # Custom backend port
frontend_port = 3000        # Custom frontend port
auto_reload = false         # Disable uvicorn auto-reload
```

## Acceptance Criteria

✅ Config values override defaults when provided
✅ Functions work with `config=None` (backwards compatible)
✅ Port checking uses config values
✅ Subprocess commands use config values
✅ Startup messages show actual ports being used
✅ Type hints use Optional['WebConfig'] for forward references

## Dependencies
- Task 01: Base `web_launcher.py` implementation
- Task 03: Integration in `main.py`

## Notes

This task is **optional** and can be implemented later. The core functionality in Tasks 01-03 works without it using hardcoded defaults.
