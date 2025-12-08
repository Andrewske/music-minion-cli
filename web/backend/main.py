from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Music Minion Web API", version="1.0.0")

# CORS middleware for development (localhost:5173 for Vite dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers - TODO: Import when routers are implemented
# from web.backend.routers import comparisons, tracks
# app.include_router(comparisons.router, prefix="/api", tags=["comparisons"])
# app.include_router(tracks.router, prefix="/api", tags=["tracks"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
