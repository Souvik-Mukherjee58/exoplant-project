"""Main FastAPI application for ExoSignal."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings

app = FastAPI(
    title="ExoSignal API",
    description="AI-Assisted Exoplanet Technosignature Target Prioritization System",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "ExoSignal API",
        "version": "0.1.0",
        "description": "Exoplanet Technosignature Target Prioritization",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


# Include API routers
from .api import v1

app.include_router(v1.router, prefix="/api/v1", tags=["v1"])