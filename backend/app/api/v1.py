"""API v1 endpoints for ExoSignal."""

from fastapi import APIRouter, HTTPException, Query, status
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import pandas as pd
import numpy as np
import logging

from app.services.data_processor import get_data_processor

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models for API responses with validation
class PlanetResponse(BaseModel):
    planet_name: str = Field(..., description="Name of the exoplanet")
    target_priority_score: float = Field(..., ge=0.0, le=100.0, description="Priority score (0-100)")
    planet_radius: Optional[float] = Field(None, description="Planet radius in Earth radii")
    planet_mass: Optional[float] = Field(None, description="Planet mass in Earth masses")
    orbital_period: Optional[float] = Field(None, description="Orbital period in days")
    equilibrium_temperature: Optional[float] = Field(None, description="Equilibrium temperature in Kelvin")
    distance: Optional[float] = Field(None, description="Distance to star system in parsecs")
    hz_status: Optional[str] = Field(None, description="Habitable zone status")
    anomaly_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Anomaly score (0-1)")
    discovery_method: Optional[str] = Field(None, description="Discovery method")

    @field_validator('target_priority_score')
    @classmethod
    def validate_priority_score(cls, v):
        if not 0 <= v <= 100:
            raise ValueError('Priority score must be between 0 and 100')
        return v

class PlanetDetailResponse(PlanetResponse):
    priority_components: dict = Field(..., description="Breakdown of priority score components")
    stellar_effective_temperature: Optional[float] = Field(None, description="Stellar effective temperature in Kelvin")
    stellar_radius: Optional[float] = Field(None, description="Stellar radius in solar radii")
    stellar_mass: Optional[float] = Field(None, description="Stellar mass in solar masses")
    stellar_metallicity: Optional[float] = Field(None, description="Stellar metallicity")
    stellar_name: Optional[str] = Field(None, description="Name of host star")
    earth_similarity: Optional[float] = Field(None, ge=0.0, le=1.0, description="Earth similarity index (0-1)")
    observational_accessibility: Optional[float] = Field(None, ge=0.0, le=1.0, description="Observational accessibility (0-1)")
    data_quality: Optional[float] = Field(None, ge=0.0, le=1.0, description="Data quality score (0-1)")

class AnalysisResponse(BaseModel):
    total_planets: int = Field(..., ge=0, description="Total number of planets in dataset")
    score_distribution: dict = Field(..., description="Statistics of priority scores")
    priority_histogram: Optional[List[dict]] = Field(default=None, description="Actual histogram bins and counts for priority scores")
    top_targets: List[PlanetResponse] = Field(..., description="Top priority targets")
    anomaly_distribution: dict = Field(..., description="Statistics of anomaly scores")
    hz_distribution: dict = Field(..., description="Distribution of habitable zone statuses")
    discovery_method_distribution: dict = Field(..., description="Distribution of discovery methods")

class AnomalyPCAResponse(BaseModel):
    planets: List[str] = Field(..., description="Planet names")
    pca_x: List[float] = Field(..., description="PCA x-coordinates")
    pca_y: List[float] = Field(..., description="PCA y-coordinates")
    anomaly_score: List[float] = Field(..., description="Anomaly scores")
    target_priority_score: List[float] = Field(..., description="Priority scores")
    hz_status: List[str] = Field(..., description="Habitable zone statuses")
    explained_variance: List[float] = Field(..., description="PCA explained variance ratios")
    feature_names: List[str] = Field(..., description="Feature names used in PCA")


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
def get_planets(
    limit: int = Query(100, ge=1, le=500, description="Maximum number of planets to return"),
    offset: int = Query(0, ge=0, description="Number of planets to skip"),
    min_priority: float = Query(0.0, ge=0.0, le=100.0, description="Minimum priority score filter"),
    max_priority: float = Query(100.0, ge=0.0, le=100.0, description="Maximum priority score filter"),
    q: Optional[str] = Query(None, description="Search term for planet name substring"),
    hz_status: Optional[str] = Query(None, description="Filter by habitable zone status (Inside HZ, Near HZ, Outside HZ)")
):
    """
    Get list of exoplanets with priority scores.

    Supports filtering by priority score range, search query, habitable zone status, and pagination.
    """
    if min_priority > max_priority:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"min_priority ({min_priority}) cannot be greater than max_priority ({max_priority})"
        )

    try:
        processor = get_data_processor()
        df = processor.get_processed_data()

        if df.empty:
            logger.warning("No processed data available")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Exoplanet data service is currently unavailable or initializing."
            )

        # Apply priority filters
        df = df[
            (df["target_priority_score"] >= min_priority) &
            (df["target_priority_score"] <= max_priority)
        ]

        # Apply search query filter if provided
        if q and q.strip():
            query_clean = q.strip().casefold()
            df = df[df["planet_name"].astype(str).str.casefold().str.contains(query_clean, na=False, regex=False)]

        # Apply HZ status filter if provided
        if hz_status and hz_status.strip():
            hz_clean = hz_status.strip().casefold()
            df = df[df["hz_status"].astype(str).str.casefold() == hz_clean]

        if df.empty:
            logger.info(f"No planets matched filter criteria (q={q}, hz={hz_status}, score={min_priority}-{max_priority})")
            return []

        # Pagination
        df = df.iloc[offset:offset+limit]

        # Convert to response format
        planets = [_row_to_planet_response(row) for _, row in df.iterrows()]

        logger.info(f"Returning {len(planets)} planets (offset={offset}, limit={limit})")
        return planets

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Value error in get_planets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Data processing error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_planets: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving planet data"
        )


@router.get("/planets/{planet_name}", response_model=PlanetDetailResponse)
def get_planet_details(planet_name: str):
    """
    Get detailed information for a specific exoplanet.

    Performs case-insensitive exact matching on planet names.
    """
    try:
        if not planet_name or len(planet_name.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Planet name cannot be empty"
            )

        processor = get_data_processor()
        planet_row = processor.get_planet_by_name(planet_name)

        if planet_row is None:
            logger.warning(f"Planet not found: {planet_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Planet '{planet_name}' not found in the dataset"
            )

        return _row_to_planet_detail_response(planet_row)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_planet_details for {planet_name}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving planet details"
        )


@router.get("/top-targets", response_model=List[PlanetResponse])
def get_top_targets(
    limit: int = Query(10, ge=1, le=500, description="Maximum number of top targets to return"),
    min_priority: float = Query(0.0, ge=0.0, le=100.0, description="Minimum priority score threshold")
):
    """
    Get top priority targets.

    Returns planets with the highest priority scores above the specified threshold.
    """
    try:
        processor = get_data_processor()
        df = processor.get_top_targets(limit=limit, min_priority=min_priority)

        if df.empty:
            logger.info(f"No top targets found with min_priority={min_priority}")
            return []

        return [_row_to_planet_response(row) for _, row in df.iterrows()]

    except ValueError as e:
        logger.error(f"Value error in get_top_targets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Data processing error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_top_targets: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving top targets"
        )


@router.get("/analysis", response_model=AnalysisResponse)
def get_analysis():
    """
    Get overall analysis and statistics.

    Returns system-wide statistics including score distributions,
    real histogram bins, top targets, and various breakdowns.
    """
    try:
        processor = get_data_processor()
        stats = processor.get_stats()

        # Get top targets
        top_df = processor.get_top_targets(limit=10)
        top_targets = [_row_to_planet_response(row) for _, row in top_df.iterrows()]

        return AnalysisResponse(
            total_planets=stats["total_planets"],
            score_distribution=stats["score_distribution"],
            priority_histogram=stats.get("priority_histogram"),
            top_targets=top_targets,
            anomaly_distribution=stats["anomaly_distribution"],
            hz_distribution=stats["hz_distribution"],
            discovery_method_distribution=stats["discovery_method_distribution"]
        )

    except ValueError as e:
        logger.error(f"Value error in get_analysis: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Data processing error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving analysis data"
        )


@router.get("/anomaly-pca", response_model=AnomalyPCAResponse)
def get_anomaly_pca():
    """
    Get PCA data for anomaly visualization.

    Returns 2D PCA projection of exoplanet features along with
    anomaly scores and other metadata for visualization.
    """
    try:
        processor = get_data_processor()
        pca_data = processor.get_anomaly_pca_data()

        if "error" in pca_data:
            logger.warning(f"PCA error: {pca_data['error']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=pca_data["error"]
            )

        return AnomalyPCAResponse(**pca_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_anomaly_pca: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving PCA data"
        )

