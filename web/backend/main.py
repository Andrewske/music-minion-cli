import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging for web backend
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="Music Minion Web API", version="1.0.0")

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
from .routers import comparisons, tracks, stats, builder
from .routers.playlists import router as playlists_router

app.include_router(comparisons.router, prefix="/api", tags=["comparisons"])
app.include_router(tracks.router, prefix="/api", tags=["tracks"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(playlists_router, prefix="/api", tags=["playlists"])
app.include_router(builder.router, prefix="/api/builder", tags=["builder"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
