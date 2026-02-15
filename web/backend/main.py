import os
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse

from music_minion.core.config import get_data_dir

# Configure logging for web backend
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="Music Minion Web API", version="1.0.0")

# Mount custom emojis static files
custom_emojis_dir = get_data_dir() / "custom_emojis"
custom_emojis_dir.mkdir(exist_ok=True)
app.mount(
    "/custom_emojis",
    StaticFiles(directory=str(custom_emojis_dir)),
    name="custom_emojis"
)

# CORS: Allow environment override for production
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = (
    allowed_origins_env.split(",")
    if allowed_origins_env
    else ["http://localhost:5173"]  # Dev default
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from .routers import comparisons, tracks, stats, youtube, soundcloud, builder, sync, live, emojis, player
from .routers.playlists import router as playlists_router

app.include_router(comparisons.router, prefix="/api", tags=["comparisons"])
app.include_router(tracks.router, prefix="/api", tags=["tracks"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(playlists_router, prefix="/api", tags=["playlists"])
app.include_router(builder.router, prefix="/api/builder", tags=["builder"])
app.include_router(emojis.router, prefix="/api", tags=["emojis"])
app.include_router(youtube.router, prefix="/api/youtube", tags=["youtube"])
app.include_router(soundcloud.router, prefix="/api/soundcloud", tags=["soundcloud"])
app.include_router(sync.router, prefix="/api", tags=["sync"])
app.include_router(player.router, prefix="/api/player", tags=["player"])
app.include_router(live.router, tags=["live"])


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    from music_minion.core.db_adapter import is_postgres, init_postgres_schema

    if is_postgres():
        logging.info("PostgreSQL detected, initializing schema...")
        init_postgres_schema()
    else:
        # SQLite - use existing init
        from music_minion.core.database import init_database
        init_database()


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


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
    logging.info(f"Frontend dist not found at {FRONTEND_DIST}, skipping static file serving")
