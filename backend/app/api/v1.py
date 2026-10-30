"""API v1 endpoints for ExoSignal."""

import ast
import logging
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from app.ml.explainability import SHAPExplainer
from app.services.query_engine import CatalogQueryEngine

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models for API responses with validation
class PlanetResponse(BaseModel):
    planet_name: str = Field(..., description="Name of the exoplanet")
    priority_score: Optional[float] = Field(None, ge=0.0, le=100.0, description="Supervised ML priority score (0-100)")
    priority_rank: Optional[int] = Field(
        None, ge=1, description="Rank among eligible planets (1 = top target; None for ineligible)"
    )
    heuristic_habitability_score: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Heuristic habitability score (0-100)"
    )
    target_priority_score: float = Field(..., ge=0.0, le=100.0, description="Heuristic priority score (0-100)")
    ml_priority_score: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Supervised LTR priority score (0-100)"
    )
    ml_rank: Optional[int] = Field(None, ge=1, description="Rank under supervised Learning-to-Rank model")
    rank_delta: Optional[int] = Field(
        None, description="Rank shift between heuristic and ML (positive = ML ranks higher)"
    )
    planet_radius: Optional[float] = Field(None, description="Planet radius in Earth radii")
    planet_mass: Optional[float] = Field(None, description="Planet mass in Earth masses")
    orbital_period: Optional[float] = Field(None, description="Orbital period in days")
    equilibrium_temperature: Optional[float] = Field(None, description="Equilibrium temperature in Kelvin")
    distance: Optional[float] = Field(None, description="Distance to star system in parsecs")
    hz_status: Optional[str] = Field(None, description="Habitable zone status")
    anomaly_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Anomaly score (0-1)")
    discovery_method: Optional[str] = Field(None, description="Discovery method")
    is_transiting: Optional[bool] = Field(None, description="Whether the planet transits its host star")
    eligible_for_transmission: Optional[bool] = Field(None, description="Eligibility for transmission spectroscopy")
    exclusion_reason: Optional[str] = Field(None, description="Exclusion reason if ineligible")
    already_observed_jwst: Optional[bool] = Field(None, description="Whether target has been observed by JWST")
    tsm: Optional[float] = Field(None, description="Transmission Spectroscopy Metric")
    tsm_threshold: Optional[float] = Field(None, description="Kempton et al. (2018) size-class threshold")
    kempton_size_class: Optional[str] = Field(None, description="Kempton et al. (2018) physical regime")
    percentile_rank: Optional[float] = Field(None, description="Percentile rank (0-100%, lower is higher priority)")
    percentile_rank_string: Optional[str] = Field(
        None, description="Human-readable percentile rank ('Top X.X% of 4,643 eligible planets')"
    )
    oof_ml_rank: Optional[int] = Field(None, description="Out-of-fold global model rank")
    oof_priority_score: Optional[float] = Field(None, description="Out-of-fold cross-validated priority score")
    unobserved_rank: Optional[int] = Field(None, description="Rank among unobserved candidates")

    @field_validator("target_priority_score")
    @classmethod
    def validate_priority_score(cls, v):
        if not 0 <= v <= 100:
            raise ValueError("Priority score must be between 0 and 100")
        return v


class PlanetDetailResponse(PlanetResponse):
    priority_components: dict = Field(..., description="Breakdown of priority score components")
    stellar_effective_temperature: Optional[float] = Field(None, description="Stellar effective temperature in Kelvin")
    stellar_radius: Optional[float] = Field(None, description="Stellar radius in solar radii")
    stellar_mass: Optional[float] = Field(None, description="Stellar mass in solar masses")
    stellar_metallicity: Optional[float] = Field(None, description="Stellar metallicity")
    stellar_name: Optional[str] = Field(None, description="Name of host star")
    earth_similarity: Optional[float] = Field(None, ge=0.0, le=1.0, description="Earth similarity index (0-1)")
    observational_accessibility: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Observational accessibility (0-1)"
    )
    data_quality: Optional[float] = Field(None, ge=0.0, le=1.0, description="Data quality score (0-1)")


class RecommendationResponse(BaseModel):
    planet_name: str = Field(..., description="Name of the exoplanet")
    rank: int = Field(..., description="Recommendation priority rank")
    priority_score: float = Field(..., description="Priority score")
    percentile_rank: Optional[float] = Field(None, description="Percentile rank number")
    percentile_rank_string: Optional[str] = Field(None, description="Percentile rank label")
    tsm: Optional[float] = Field(None, description="Transmission Spectroscopy Metric")
    tsm_threshold: Optional[float] = Field(None, description="Kempton recommended threshold")
    kempton_size_class: Optional[str] = Field(None, description="Size class regime")
    tsm_ratio: Optional[float] = Field(None, description="Ratio of TSM to threshold")
    already_observed_jwst: bool = Field(False, description="Whether target has been observed by JWST")
    reasons: List[str] = Field(default_factory=list, description="Top 3 SHAP drivers in plain English")
    planet_radius: Optional[float] = None
    planet_mass: Optional[float] = None
    orbital_period: Optional[float] = None
    equilibrium_temperature: Optional[float] = None
    distance: Optional[float] = None
    stellar_name: Optional[str] = None
    hz_status: Optional[str] = None
    anomaly_score: Optional[float] = None


class AnalysisResponse(BaseModel):
    total_planets: int = Field(..., ge=0, description="Total number of planets in dataset")
    score_distribution: dict = Field(..., description="Statistics of priority scores")
    priority_histogram: Optional[List[dict]] = Field(
        default=None, description="Actual histogram bins and counts for priority scores"
    )
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


class WaterfallItem(BaseModel):
    feature: str = Field(..., description="Machine learning feature identifier")
    display_name: str = Field(..., description="Human-readable physical feature title")
    description: str = Field(..., description="Physical domain description")
    raw_value: str = Field(..., description="Formatted physical value with units")
    shap_value: float = Field(..., description="Raw TreeSHAP contribution in log-odds margin space")
    score_impact: float = Field(..., description="Calibrated priority score impact (points)")
    direction: str = Field(..., description="'positive' driver or 'negative' barrier")
    abs_importance: float = Field(..., description="Absolute TreeSHAP magnitude")


class MathematicalInvariants(BaseModel):
    base_margin: float = Field(..., description="Global expected baseline margin")
    sum_shap_margin: float = Field(..., description="Sum of all individual feature SHAP contributions")
    predicted_margin: float = Field(..., description="Model predicted margin")
    reconstruction_error: float = Field(
        ..., description="Residual reconstruction error (|sum(phi) + base - predicted|)"
    )


class PlanetExplanationResponse(BaseModel):
    planet_name: str = Field(..., description="Exoplanet identifier")
    ml_priority_score: float = Field(..., ge=0.0, le=100.0, description="Predicted ML priority score")
    base_score: float = Field(..., ge=0.0, le=100.0, description="Expected baseline score across population")
    score_delta_from_base: float = Field(..., description="Net score shift attributed to planetary features")
    mathematical_invariants: MathematicalInvariants = Field(..., description="TreeSHAP additive conservation proof")
    top_positive_drivers: List[WaterfallItem] = Field(..., description="Top 5 features elevating priority")
    top_negative_barriers: List[WaterfallItem] = Field(..., description="Top 5 features lowering priority")
    full_waterfall: List[WaterfallItem] = Field(
        ..., description="All 21 feature contributions ordered by absolute impact"
    )


class DifferentialWaterfallItem(BaseModel):
    feature: str = Field(..., description="Feature identifier")
    display_name: str = Field(..., description="Human-readable physical title")
    planet_a_value: str = Field(..., description="Target A formatted physical value")
    planet_b_value: str = Field(..., description="Target B formatted physical value")
    diff_shap: float = Field(..., description="Delta TreeSHAP (phi_A - phi_B)")
    diff_score_impact: float = Field(..., description="Net score impact difference in points")
    advantage: str = Field(..., description="Favored target ('Planet A' or 'Planet B')")
    abs_diff: float = Field(..., description="Absolute differential magnitude")


class ComparisonExplanationResponse(BaseModel):
    planet_a: str = Field(..., description="First planet identifier")
    planet_b: str = Field(..., description="Second planet identifier")
    planet_a_score: float = Field(..., ge=0.0, le=100.0, description="Target A ML priority score")
    planet_b_score: float = Field(..., ge=0.0, le=100.0, description="Target B ML priority score")
    score_advantage: float = Field(..., description="Score difference (Target A - Target B)")
    primary_drivers_for_advantage: List[DifferentialWaterfallItem] = Field(
        ..., description="Top features favoring Target A"
    )
    primary_drivers_for_disadvantage: List[DifferentialWaterfallItem] = Field(
        ..., description="Top features favoring Target B"
    )
    differential_waterfall: List[DifferentialWaterfallItem] = Field(..., description="All differential attributions")


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
    """Convert a DataFrame row to PlanetResponse with unified One Score, One Rank."""
    p_score = _clean_val(row.get("priority_score"))
    if p_score is None:
        p_score = _clean_val(row.get("ml_priority_score"))
    if p_score is None:
        p_score = float(row.get("target_priority_score", 0.0))

    ml_r = int(row["ml_rank"]) if pd.notna(row.get("ml_rank")) else None
    p_rank = int(row["priority_rank"]) if pd.notna(row.get("priority_rank")) else ml_r

    heur_score = _clean_val(row.get("heuristic_habitability_score"))
    if heur_score is None:
        heur_score = float(row.get("target_priority_score", 0.0))

    return PlanetResponse(
        planet_name=row.get("planet_name", ""),
        priority_score=p_score,
        priority_rank=p_rank,
        heuristic_habitability_score=heur_score,
        target_priority_score=float(row.get("target_priority_score", heur_score or 0.0)),
        ml_priority_score=_clean_val(row.get("ml_priority_score")) or p_score,
        ml_rank=ml_r or p_rank,
        rank_delta=int(row["rank_delta"]) if pd.notna(row.get("rank_delta")) else None,
        planet_radius=_clean_val(row.get("planet_radius")),
        planet_mass=_clean_val(row.get("planet_mass")),
        orbital_period=_clean_val(row.get("orbital_period")),
        equilibrium_temperature=_clean_val(row.get("equilibrium_temperature")),
        distance=_clean_val(row.get("distance")),
        hz_status=_clean_val(row.get("hz_status")),
        anomaly_score=_clean_val(row.get("anomaly_score")),
        discovery_method=_clean_val(row.get("discovery_method")),
        is_transiting=_clean_val(row.get("is_transiting")),
        eligible_for_transmission=_clean_val(row.get("eligible_for_transmission")),
        exclusion_reason=_clean_val(row.get("exclusion_reason")),
        already_observed_jwst=bool(row.get("already_observed_jwst") or row.get("is_jwst_target"))
        if pd.notna(row.get("already_observed_jwst")) or pd.notna(row.get("is_jwst_target"))
        else None,
        tsm=_clean_val(row.get("tsm")),
        tsm_threshold=_clean_val(row.get("tsm_threshold")),
        kempton_size_class=_clean_val(row.get("kempton_size_class")),
        percentile_rank=_clean_val(row.get("percentile_rank")),
        percentile_rank_string=_clean_val(row.get("percentile_rank_string")),
        oof_ml_rank=int(row["oof_ml_rank"]) if pd.notna(row.get("oof_ml_rank")) else None,
        oof_priority_score=_clean_val(row.get("oof_priority_score")),
        unobserved_rank=int(row["unobserved_rank"]) if pd.notna(row.get("unobserved_rank")) else None,
    )


def _row_to_planet_detail_response(row: pd.Series) -> PlanetDetailResponse:
    """Convert a DataFrame row to PlanetDetailResponse with unified One Score, One Rank."""
    p_score = _clean_val(row.get("priority_score"))
    if p_score is None:
        p_score = _clean_val(row.get("ml_priority_score"))
    if p_score is None:
        p_score = float(row.get("target_priority_score", 0.0))

    ml_r = int(row["ml_rank"]) if pd.notna(row.get("ml_rank")) else None
    p_rank = int(row["priority_rank"]) if pd.notna(row.get("priority_rank")) else ml_r

    heur_score = _clean_val(row.get("heuristic_habitability_score"))
    if heur_score is None:
        heur_score = float(row.get("target_priority_score", 0.0))

    return PlanetDetailResponse(
        planet_name=row.get("planet_name", ""),
        priority_score=p_score,
        priority_rank=p_rank,
        heuristic_habitability_score=heur_score,
        target_priority_score=float(row.get("target_priority_score", heur_score or 0.0)),
        ml_priority_score=_clean_val(row.get("ml_priority_score")) or p_score,
        ml_rank=ml_r or p_rank,
        rank_delta=int(row["rank_delta"]) if pd.notna(row.get("rank_delta")) else None,
        planet_radius=_clean_val(row.get("planet_radius")),
        planet_mass=_clean_val(row.get("planet_mass")),
        orbital_period=_clean_val(row.get("orbital_period")),
        equilibrium_temperature=_clean_val(row.get("equilibrium_temperature")),
        distance=_clean_val(row.get("distance")),
        hz_status=_clean_val(row.get("hz_status")),
        anomaly_score=_clean_val(row.get("anomaly_score")),
        discovery_method=_clean_val(row.get("discovery_method")),
        is_transiting=_clean_val(row.get("is_transiting")),
        eligible_for_transmission=_clean_val(row.get("eligible_for_transmission")),
        exclusion_reason=_clean_val(row.get("exclusion_reason")),
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
    hz_status: Optional[str] = Query(
        None, description="Filter by habitable zone status (Inside HZ, Near HZ, Outside HZ)"
    ),
    sort_by: str = Query(
        "priority",
        pattern="^(priority|heuristic|ml)$",
        description="Ranking scheme: 'priority' (default, Supervised ML) or 'heuristic'",
    ),
):
    """
    Get list of exoplanets with priority scores via vectorized DuckDB engine.

    Executes parameterized SQL with predicate pushdown over Parquet storage.
    """
    if min_priority > max_priority:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"min_priority ({min_priority}) cannot be greater than max_priority ({max_priority})",
        )

    try:
        engine = CatalogQueryEngine.get_instance()
        planets = engine.query_planets(
            limit=limit,
            offset=offset,
            min_priority=min_priority,
            max_priority=max_priority,
            q=q,
            hz_status=hz_status,
            sort_by=sort_by,
        )
        return [_row_to_planet_response(p) for p in planets]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_planets via DuckDB: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while querying planet catalog",
        )


@router.get("/planets/compare-explain", response_model=ComparisonExplanationResponse)
def get_comparison_explanation(
    planet_a: str = Query(..., description="Target name of first exoplanet"),
    planet_b: str = Query(..., description="Target name of second exoplanet"),
):
    """
    Differential TreeSHAP attribution: explains ranking differentials between two planets.

    Computes Delta_phi_i = phi_i(A) - phi_i(B) to isolate why Planet A ranks higher or lower than Planet B.
    """
    try:
        if not planet_a.strip() or not planet_b.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Both planet_a and planet_b must be non-empty strings"
            )

        engine = CatalogQueryEngine.get_instance()
        row_a = engine.get_planet_by_name(planet_a)
        if row_a is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Planet A '{planet_a}' not found in catalog"
            )

        row_b = engine.get_planet_by_name(planet_b)
        if row_b is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Planet B '{planet_b}' not found in catalog"
            )

        explainer = SHAPExplainer.get_instance()
        return explainer.explain_comparison(row_a, row_b)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing planets {planet_a} vs {planet_b}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute differential TreeSHAP explanation: {str(e)}",
        )


@router.get("/planets/{planet_name}/explain", response_model=PlanetExplanationResponse)
@router.get("/explain/{planet_name}", response_model=PlanetExplanationResponse)
def get_planet_explanation(planet_name: str):
    """
    Compute exact TreeSHAP feature attribution waterfall and ranking drivers for an individual exoplanet.

    Guarantees the mathematical conservation invariant: sum(phi_i) + base_margin = predicted_margin.
    """
    try:
        if not planet_name or len(planet_name.strip()) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Planet name cannot be empty")

        engine = CatalogQueryEngine.get_instance()
        planet_row = engine.get_planet_by_name(planet_name)

        if planet_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Planet '{planet_name}' not found in the dataset"
            )

        explainer = SHAPExplainer.get_instance()
        return explainer.explain_planet(planet_row)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error explaining planet {planet_name}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute TreeSHAP explanation: {str(e)}",
        )


@router.get("/planets/{planet_name}", response_model=PlanetDetailResponse)
def get_planet_details(planet_name: str):
    """
    Get detailed information for a specific exoplanet via DuckDB.

    Performs case-insensitive exact matching with sub-millisecond index lookup.
    """
    try:
        if not planet_name or len(planet_name.strip()) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Planet name cannot be empty")

        engine = CatalogQueryEngine.get_instance()
        planet_row = engine.get_planet_by_name(planet_name)

        if planet_row is None:
            logger.warning(f"Planet not found: {planet_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Planet '{planet_name}' not found in the dataset"
            )

        return _row_to_planet_detail_response(planet_row)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_planet_details for {planet_name}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving planet details",
        )


@router.get("/top-targets", response_model=List[PlanetResponse])
def get_top_targets(
    limit: int = Query(10, ge=1, le=500, description="Maximum number of top targets to return"),
    min_priority: float = Query(0.0, ge=0.0, le=100.0, description="Minimum priority score threshold"),
    sort_by: str = Query(
        "priority",
        pattern="^(priority|heuristic|ml)$",
        description="Ranking scheme: 'priority' (default, Supervised ML) or 'heuristic'",
    ),
    exclude_observed: bool = Query(
        True, description="Exclude planets already in an approved JWST transmission program"
    ),
):
    """
    Get top priority targets via vectorized DuckDB index scan.
    Main ranking defaults to unobserved candidate targets only.
    """
    try:
        engine = CatalogQueryEngine.get_instance()
        targets = engine.get_top_targets(
            limit=limit, min_priority=min_priority, sort_by=sort_by, exclude_observed=exclude_observed
        )
        return [_row_to_planet_response(t) for t in targets]

    except Exception as e:
        logger.error(f"Error in get_top_targets: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving top targets",
        )


@router.get("/validation/known-targets", response_model=List[PlanetResponse])
def get_known_jwst_targets():
    """
    Validation view: shows where confirmed JWST atmospheric targets land using out-of-fold ranks only.
    """
    try:
        engine = CatalogQueryEngine.get_instance()
        planets = engine.get_known_jwst_targets()
        return [_row_to_planet_response(p) for p in planets]
    except Exception as e:
        logger.error(f"Error in get_known_jwst_targets: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving known targets",
        )


@router.get("/recommendations", response_model=List[RecommendationResponse])
def get_recommendations(
    exclude_observed: bool = Query(True, description="Exclude planets already observed by JWST"),
    size_class: Optional[str] = Query(
        None, description="Filter by size class: terrestrial, small_sub_neptune, large_sub_neptune, gas_giant"
    ),
    limit: int = Query(25, ge=1, le=100, description="Maximum recommendations to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Get prioritized target recommendations with plain-English scientific justifications.
    Filters out already-observed JWST targets by default and supports size class sub-filtering.
    """
    try:
        engine = CatalogQueryEngine.get_instance()
        planets = engine.get_recommendations(
            limit=limit, offset=offset, exclude_observed=exclude_observed, size_class=size_class
        )
        explainer = SHAPExplainer.get_instance()
        from app.ml.explainability import get_plain_english_reasons_for_planet

        results = []
        for idx, p in enumerate(planets):
            rank = int(p.get("unobserved_rank") or p.get("priority_rank") or (offset + idx + 1))
            score = float(
                p.get("priority_score") or p.get("ml_priority_score") or p.get("target_priority_score") or 0.0
            )
            tsm_val = _clean_val(p.get("tsm"))
            thresh_val = _clean_val(p.get("tsm_threshold"))
            ratio = round(tsm_val / thresh_val, 2) if (tsm_val is not None and thresh_val and thresh_val > 0) else None

            # Generate top 3 SHAP drivers in plain English
            try:
                reasons = get_plain_english_reasons_for_planet(p, explainer=explainer)
            except Exception:
                reasons = []

            results.append(
                RecommendationResponse(
                    planet_name=p.get("planet_name", ""),
                    rank=rank,
                    priority_score=score,
                    percentile_rank=_clean_val(p.get("percentile_rank")),
                    percentile_rank_string=_clean_val(p.get("percentile_rank_string")),
                    tsm=tsm_val,
                    tsm_threshold=thresh_val,
                    kempton_size_class=_clean_val(p.get("kempton_size_class")),
                    tsm_ratio=ratio,
                    already_observed_jwst=bool(p.get("already_observed_jwst") or p.get("is_jwst_target")),
                    reasons=reasons,
                    planet_radius=_clean_val(p.get("planet_radius")),
                    planet_mass=_clean_val(p.get("planet_mass")),
                    orbital_period=_clean_val(p.get("orbital_period")),
                    equilibrium_temperature=_clean_val(p.get("equilibrium_temperature")),
                    distance=_clean_val(p.get("distance")),
                    stellar_name=_clean_val(p.get("stellar_name")),
                    hz_status=_clean_val(p.get("hz_status")),
                    anomaly_score=_clean_val(p.get("anomaly_score")),
                )
            )
        return results

    except Exception as e:
        logger.error(f"Error in get_recommendations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating recommendations",
        )


@router.get("/analysis", response_model=AnalysisResponse)
def get_analysis():
    """
    Get overall analysis and population statistics via vectorized DuckDB aggregations.
    """
    try:
        engine = CatalogQueryEngine.get_instance()
        stats = engine.get_analysis_stats()
        top_targets = engine.get_top_targets(limit=10)

        return AnalysisResponse(
            total_planets=stats["total_planets"],
            score_distribution=stats["score_distribution"],
            priority_histogram=stats.get("priority_histogram"),
            top_targets=[_row_to_planet_response(t) for t in top_targets],
            anomaly_distribution=stats["anomaly_distribution"],
            hz_distribution=stats["hz_distribution"],
            discovery_method_distribution=stats["discovery_method_distribution"],
        )

    except Exception as e:
        logger.error(f"Error in get_analysis via DuckDB: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while calculating analysis statistics",
        )


@router.get("/system/latency-benchmark")
def get_latency_benchmark(
    iterations: int = Query(100, ge=10, le=500, description="Number of query iterations to benchmark"),
):
    """
    Benchmark real-time vectorized DuckDB query engine latency over concurrent analytical queries.
    """
    try:
        engine = CatalogQueryEngine.get_instance()
        return engine.benchmark_latency(iterations=iterations)
    except Exception as e:
        logger.error(f"Error executing latency benchmark: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to benchmark query latency: {str(e)}"
        )


@router.get("/anomaly-pca", response_model=AnomalyPCAResponse)
def get_anomaly_pca():
    """
    Get PCA data for anomaly visualization from in-memory preloaded artifact.

    Returns 2D PCA projection of exoplanet features along with
    anomaly scores and other metadata for visualization.
    """
    try:
        engine = CatalogQueryEngine.get_instance()
        pca_data = engine.get_precomputed_pca()

        if "error" in pca_data:
            logger.warning(f"PCA error: {pca_data['error']}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=pca_data["error"])

        return AnomalyPCAResponse(**pca_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_anomaly_pca: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving PCA data",
        )


@router.get("/evaluation/benchmark")
def get_evaluation_benchmark(
    split: str = Query(
        "test",
        pattern="^(test|val)$",
        description="Dataset split to evaluate: 'test' (out-of-time >=2022) or 'val' (2018-2021)",
    ),
):
    """
    Get offline ML ranking evaluation benchmark leaderboard and metrics from in-memory artifact.

    Evaluates models (Random, Distance, ESI, ExoSignal Composite, Supervised GBDT)
    against published ground truth (Kempton et al. 2018 TSM and confirmed JWST atmospheric targets).
    """
    try:
        engine = CatalogQueryEngine.get_instance()
        report = engine.get_benchmark_report(split=split)
        return report
    except Exception as e:
        logger.error(f"Error computing evaluation benchmark: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute evaluation benchmark: {str(e)}",
        )


@router.get("/models/ltr/info")
def get_ltr_info():
    """
    Get Learning-to-Rank (LTR) model metadata, hyperparameters, and test benchmarks from in-memory manifest.
    """
    try:
        engine = CatalogQueryEngine.get_instance()
        return engine.get_ltr_info()
    except Exception as e:
        logger.error(f"Error retrieving LTR model info: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve LTR model info: {str(e)}"
        )


@router.get("/models/ltr/feature-importance")
def get_ltr_feature_importance():
    """
    Get ranked feature importances (information gain and split counts) for the LTR model from in-memory artifact.
    """
    try:
        engine = CatalogQueryEngine.get_instance()
        return engine.get_ltr_feature_importances()
    except Exception as e:
        logger.error(f"Error retrieving LTR feature importances: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve LTR feature importances: {str(e)}",
        )


# ================================================================
# Model Registry Endpoints
# ================================================================


class RollbackRequest(BaseModel):
    reason: str = Field("", description="Reason for rolling back production model version")


class PromoteRequest(BaseModel):
    reason: str = Field("", description="Reason for promoting model version to production")


@router.get("/models/registry/versions")
def list_registered_versions():
    """
    List all model versions tracked in the Model Registry,
    including their deployment status, offline evaluation metrics, and registration date.
    """
    try:
        from app.ml.model_registry import ModelRegistry

        registry = ModelRegistry()
        active = registry.get_active_version()
        versions = registry.list_versions()
        return {"active_version": active, "total_versions": len(versions), "versions": versions}
    except Exception as e:
        logger.error(f"Error listing model registry versions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list model registry versions: {str(e)}",
        )


@router.get("/models/registry/active")
def get_active_model_version():
    """
    Get full metadata, provenance, and SHA256 integrity checksums
    for the currently deployed production model.
    """
    try:
        from app.ml.model_registry import ModelRegistry

        registry = ModelRegistry()
        active_ver = registry.get_active_version()
        if not active_ver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No active model version set in registry."
            )
        entry = registry.get_version(active_ver)
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Active version '{active_ver}' not found in registry index.",
            )
        return entry
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving active model version: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve active model version: {str(e)}",
        )


@router.get("/models/registry/validate/{version}")
def validate_model_integrity(version: str):
    """
    Perform cryptographic integrity validation on serialized model and parquet catalog artifacts
    for a given version. Detects file tampering or silent disk corruption.
    """
    try:
        from app.ml.model_registry import ModelRegistry

        registry = ModelRegistry()
        report = registry.validate_integrity(version)
        if not report.get("valid") and "error" in report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=report["error"])
        return report
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error validating model integrity: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to validate model integrity: {str(e)}"
        )


@router.get("/models/registry/compare")
def compare_model_versions(
    version_a: str = Query(..., description="First version tag (candidate)"),
    version_b: str = Query(..., description="Second version tag (baseline)"),
):
    """
    Compare offline evaluation metrics (NDCG@10, MAP, PR-AUC), training configs,
    and dataset sizes between two registered model versions.
    """
    try:
        from app.ml.model_registry import ModelRegistry

        registry = ModelRegistry()
        comparison = registry.compare_versions(version_a, version_b)
        return comparison
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error comparing model versions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to compare model versions: {str(e)}"
        )


@router.post("/models/registry/promote/{version}")
def promote_model_version(version: str, req: Optional[PromoteRequest] = None):
    """
    Promote a registered model version to active production status.
    Updates the active pointer and records an immutable audit trail entry.
    """
    try:
        from app.ml.model_registry import ModelRegistry

        registry = ModelRegistry()
        reason = req.reason if req else "Promoted via API"
        registry.promote(version, reason=reason)
        return {
            "status": "success",
            "promoted_version": version,
            "message": f"Successfully promoted {version} to production.",
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error promoting model version: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to promote model version: {str(e)}"
        )


@router.post("/models/registry/rollback")
def rollback_model_version(req: Optional[RollbackRequest] = None):
    """
    Instant rollback: restore the previous active production model version
    from the promotion history audit log.
    """
    try:
        from app.ml.model_registry import ModelRegistry

        registry = ModelRegistry()
        reason = req.reason if req else "Rollback triggered via API"
        restored = registry.rollback(reason=reason)
        if not restored:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No previous production version available to roll back to.",
            )
        return {
            "status": "success",
            "active_version": restored,
            "message": f"Successfully rolled back to version {restored}.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during model rollback: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to rollback model version: {str(e)}"
        )
