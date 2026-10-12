"""API v1 endpoints for ExoSignal."""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
import pandas as pd
import numpy as np

from app.services.data_processor import get_data_processor

router = APIRouter()

# Pydantic models for API responses
class PlanetResponse(BaseModel):
    planet_name: str
    target_priority_score: float
    planet_radius: Optional[float]
    planet_mass: Optional[float]
    orbital_period: Optional[float]
    equilibrium_temperature: Optional[float]
    distance: Optional[float]
    hz_status: Optional[str]
    anomaly_score: Optional[float]
    discovery_method: Optional[str]

class PlanetDetailResponse(PlanetResponse):
    priority_components: dict
    stellar_effective_temperature: Optional[float]
    stellar_radius: Optional[float]
    stellar_mass: Optional[float]
    stellar_metallicity: Optional[float]
    stellar_name: Optional[str]
    earth_similarity: Optional[float]
    observational_accessibility: Optional[float]
    data_quality: Optional[float]

class AnalysisResponse(BaseModel):
    total_planets: int
    score_distribution: dict
    top_targets: List[PlanetResponse]
    anomaly_distribution: dict
    hz_distribution: dict
    discovery_method_distribution: dict

class AnomalyPCAResponse(BaseModel):
    planets: List[str]
    pca_x: List[float]
    pca_y: List[float]
    anomaly_score: List[float]
    target_priority_score: List[float]
    hz_status: List[str]
    explained_variance: List[float]
    feature_names: List[str]


import ast


def _clean_val(val):
    if pd.isna(val):
        return None
    return val


def _parse_components(val):
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return ast.literal_eval(val)
        except Exception:
            return {}
    return {}


def _row_to_planet_response(row: pd.Series) -> PlanetResponse:
    """Convert a DataFrame row to PlanetResponse."""
    return PlanetResponse(
        planet_name=row.get("planet_name", ""),
        target_priority_score=float(row.get("target_priority_score", 0)),
        planet_radius=_clean_val(row.get("planet_radius")),
        planet_mass=_clean_val(row.get("planet_mass")),
        orbital_period=_clean_val(row.get("orbital_period")),
        equilibrium_temperature=_clean_val(row.get("equilibrium_temperature")),
        distance=_clean_val(row.get("distance")),
        hz_status=_clean_val(row.get("hz_status")),
        anomaly_score=_clean_val(row.get("anomaly_score")),
        discovery_method=_clean_val(row.get("discovery_method")),
    )


def _row_to_planet_detail_response(row: pd.Series) -> PlanetDetailResponse:
    """Convert a DataFrame row to PlanetDetailResponse."""
    return PlanetDetailResponse(
        planet_name=row.get("planet_name", ""),
        target_priority_score=float(row.get("target_priority_score", 0)),
        planet_radius=_clean_val(row.get("planet_radius")),
        planet_mass=_clean_val(row.get("planet_mass")),
        orbital_period=_clean_val(row.get("orbital_period")),
        equilibrium_temperature=_clean_val(row.get("equilibrium_temperature")),
        distance=_clean_val(row.get("distance")),
        hz_status=_clean_val(row.get("hz_status")),
        anomaly_score=_clean_val(row.get("anomaly_score")),
        discovery_method=_clean_val(row.get("discovery_method")),
        priority_components=_parse_components(row.get("priority_components", {})),
        stellar_effective_temperature=_clean_val(row.get("stellar_effective_temperature")),
        stellar_radius=_clean_val(row.get("stellar_radius")),
        stellar_mass=_clean_val(row.get("stellar_mass")),
        stellar_metallicity=_clean_val(row.get("stellar_metallicity")),
        stellar_name=_clean_val(row.get("stellar_name")),
        earth_similarity=_clean_val(row.get("earth_similarity")),
        observational_accessibility=_clean_val(row.get("observational_accessibility")),
        data_quality=_clean_val(row.get("data_quality")),
    )


@router.get("/planets", response_model=List[PlanetResponse])
async def get_planets(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    min_priority: float = Query(0.0, ge=0.0, le=100.0),
    max_priority: float = Query(100.0, ge=0.0, le=100.0)
):
    """Get list of exoplanets with priority scores."""
    try:
        processor = get_data_processor()
        df = processor.get_processed_data()

        # Apply filters
        df = df[
            (df["target_priority_score"] >= min_priority) &
            (df["target_priority_score"] <= max_priority)
        ]

        # Pagination
        df = df.iloc[offset:offset+limit]

        # Convert to response format
        planets = [_row_to_planet_response(row) for _, row in df.iterrows()]

        return planets

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/planets/{planet_name}", response_model=PlanetDetailResponse)
async def get_planet_details(planet_name: str):
    """Get detailed information for a specific exoplanet."""
    try:
        processor = get_data_processor()
        planet_row = processor.get_planet_by_name(planet_name)

        if planet_row is None:
            raise HTTPException(status_code=404, detail=f"Planet '{planet_name}' not found")

        return _row_to_planet_detail_response(planet_row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-targets", response_model=List[PlanetResponse])
async def get_top_targets(
    limit: int = Query(10, ge=1, le=500),
    min_priority: float = Query(0.0, ge=0.0, le=100.0)
):
    """Get top priority targets."""
    try:
        processor = get_data_processor()
        df = processor.get_top_targets(limit=limit, min_priority=min_priority)
        return [_row_to_planet_response(row) for _, row in df.iterrows()]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis", response_model=AnalysisResponse)
async def get_analysis():
    """Get overall analysis and statistics."""
    try:
        processor = get_data_processor()
        stats = processor.get_stats()

        # Get top targets
        top_df = processor.get_top_targets(limit=10)
        top_targets = [_row_to_planet_response(row) for _, row in top_df.iterrows()]

        return AnalysisResponse(
            total_planets=stats["total_planets"],
            score_distribution=stats["score_distribution"],
            top_targets=top_targets,
            anomaly_distribution=stats["anomaly_distribution"],
            hz_distribution=stats["hz_distribution"],
            discovery_method_distribution=stats["discovery_method_distribution"]
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomaly-pca", response_model=AnomalyPCAResponse)
async def get_anomaly_pca():
    """Get PCA data for anomaly visualization."""
    try:
        processor = get_data_processor()
        pca_data = processor.get_anomaly_pca_data()

        if "error" in pca_data:
            raise HTTPException(status_code=400, detail=pca_data["error"])

        return AnomalyPCAResponse(**pca_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

