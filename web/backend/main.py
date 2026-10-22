import os
import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from loguru import logger
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from music_minion.core.config import get_data_dir

# Configure logging for web backend
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def _startup() -> None:
    """Initialize database, restore player state, start background workers."""
    from music_minion.core.db_adapter import is_postgres, init_postgres_schema
    from .routers.player import restore_player_queue_state

    if is_postgres():
        logging.info("PostgreSQL detected, initializing schema...")
        init_postgres_schema()
    else:
        # SQLite - use existing init
        from music_minion.core.database import init_database

        init_database()

    custom_emojis_dir.mkdir(parents=True, exist_ok=True)

    # Restore player queue state from database
    await restore_player_queue_state()

    # Start background SC feed-sync daemon
    from web.backend.sc_feed_worker import start_feed_worker

    start_feed_worker()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await _startup()
    yield


app = FastAPI(title="Music Minion Web API", version="1.0.0", lifespan=lifespan)

# Mount custom emojis static files. check_dir=False defers the directory
# check to request time so importing this module never touches disk;
# startup (and the emoji processor) create the directory.
custom_emojis_dir = get_data_dir() / "custom_emojis"
app.mount(
    "/custom_emojis",
    StaticFiles(directory=str(custom_emojis_dir), check_dir=False),
    name="custom_emojis",
)

# CORS: Allow environment override for production
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
default_origins = [
    "http://localhost:5173",  # Vite dev
    "http://localhost:8081",  # Expo/Metro dev
]

allowed_origins = (
    allowed_origins_env.split(",") if allowed_origins_env else default_origins
)

# Auto-allow Tailscale origins (*.ts.net) for mobile app access
tailscale_origin = os.getenv("TAILSCALE_HOSTNAME", "")
if tailscale_origin:
    allowed_origins.append(f"http://{tailscale_origin}:8642")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from .routers import (
    artists,
    comparisons,
    tracks,
    youtube,
    soundcloud,
    builder,
    sync,
    live,
    emojis,
    player,
    commands,
    history,
    quicktag,
    buckets,
    genres,
    discovery,
    feed,
    feed_filters,
    feed_agent,
    insights,
)
from .routers.playlists import router as playlists_router

app.include_router(artists.router)
app.include_router(comparisons.router, prefix="/api", tags=["comparisons"])
app.include_router(tracks.router, prefix="/api", tags=["tracks"])
app.include_router(playlists_router, prefix="/api", tags=["playlists"])
app.include_router(builder.router, prefix="/api/builder", tags=["builder"])
app.include_router(emojis.router, prefix="/api", tags=["emojis"])
app.include_router(youtube.router, prefix="/api/youtube", tags=["youtube"])
app.include_router(soundcloud.router, prefix="/api/soundcloud", tags=["soundcloud"])
app.include_router(sync.router, prefix="/api", tags=["sync"])
app.include_router(player.router, prefix="/api/player", tags=["player"])
app.include_router(history.router, prefix="/api/history", tags=["history"])
app.include_router(live.router, tags=["live"])
app.include_router(commands.router, prefix="/api", tags=["commands"])
app.include_router(quicktag.router, prefix="/api/quicktag", tags=["quicktag"])
app.include_router(buckets.router, tags=["buckets"])
app.include_router(genres.router)
app.include_router(discovery.router)
app.include_router(feed.router)
app.include_router(feed_filters.router)
app.include_router(feed_agent.router)
app.include_router(insights.router)


@app.get("/health")
def health_check() -> JSONResponse:
    """Healthy only if the DB answers; deploys roll back on a 503."""
    from music_minion.core.database import get_db_connection

    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1 FROM schema_version LIMIT 1").fetchone()
    except sqlite3.Error as e:
        logger.exception("Health check: database unavailable")
        return JSONResponse({"status": "unhealthy", "error": str(e)}, status_code=503)
    return JSONResponse({"status": "healthy"})


# Static file serving for production (must come after all API routes)
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    logging.info(f"Serving frontend from {FRONTEND_DIST}")
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str = "") -> FileResponse:
        """Serve React SPA for all non-API routes."""
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    logging.info(
        f"Frontend dist not found at {FRONTEND_DIST}, skipping static file serving"
    )
