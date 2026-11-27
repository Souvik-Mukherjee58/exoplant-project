"""API v1 endpoints for ExoSignal."""

import ast
import logging
from typing import Any, Dict, List, Mapping, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.ml.explainability import SHAPExplainer
from app.ml.model_consistency import ExplanationsUnavailable
from app.scoring.priority_scorer import TargetPriorityScorer
from app.services.query_engine import CatalogQueryEngine

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models for API responses with validation
class PlanetResponse(BaseModel):
    planet_name: str = Field(..., description="Name of the exoplanet")
    priority_score: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Ranking score (0-100); not a probability"
    )
    priority_rank: Optional[int] = Field(
        None, ge=1, description="Rank among eligible planets (1 = top target; None for ineligible)"
    )
    heuristic_habitability_score: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Heuristic habitability score (0-100)"
    )
    target_priority_score: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Heuristic composite score (0-100); None when it is not available"
    )
    ml_priority_score: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Supervised ranking score (0-100); not a probability"
    )
    ml_rank: Optional[int] = Field(None, ge=1, description="Rank under the supervised ranking model")
    rank_delta: Optional[int] = Field(
        None, description="Rank shift between heuristic and ML (positive = ML ranks higher)"
    )
    planet_radius: Optional[float] = Field(None, description="Planet radius in Earth radii")
    planet_mass: Optional[float] = Field(None, description="Planet mass in Earth masses")
    orbital_period: Optional[float] = Field(None, description="Orbital period in days")
    equilibrium_temperature: Optional[float] = Field(None, description="Equilibrium temperature in Kelvin")
    distance: Optional[float] = Field(None, description="Distance to star system in parsecs")
    hz_status: Optional[str] = Field(None, description="Habitable zone status")
    anomaly_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Statistical outlier score (0-1), exploratory; not evidence of anything artificial",
    )
    discovery_method: Optional[str] = Field(None, description="Discovery method")
    is_transiting: Optional[bool] = Field(None, description="Whether the planet transits its host star")
    eligible_for_transmission: Optional[bool] = Field(None, description="Eligibility for transmission spectroscopy")
    exclusion_reason: Optional[str] = Field(None, description="Exclusion reason if ineligible")
    already_observed_jwst: Optional[bool] = Field(
        None, description="Labelled as observed by JWST (labels not human-verified)"
    )
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
    is_jwst_target: Optional[bool] = Field(
        None, description="Labelled as a JWST target in the artifact (labels not human-verified)"
    )
    mass_is_estimated: Optional[bool] = Field(
        None, description="True if the mass is estimated from a mass-radius relation; None if provenance unknown"
    )
    mass_source: Optional[str] = Field(
        None,
        description="measured | archive_mr_relation | chen_kipping_2017 | unknown_provenance | unavailable",
    )


class PlanetDetailResponse(PlanetResponse):
    priority_components: dict = Field(..., description="Breakdown of priority score components")
    stellar_effective_temperature: Optional[float] = Field(None, description="Stellar effective temperature in Kelvin")
    stellar_radius: Optional[float] = Field(None, description="Stellar radius in solar radii")
    stellar_mass: Optional[float] = Field(None, description="Stellar mass in solar masses")
    stellar_metallicity: Optional[float] = Field(None, description="Stellar metallicity")
    stellar_name: Optional[str] = Field(None, description="Name of host star")
    semi_major_axis: Optional[float] = Field(None, description="Orbital semi-major axis in AU")
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
    already_observed_jwst: bool = Field(False, description="Labelled as observed by JWST (labels not human-verified)")
    reasons: List[str] = Field(default_factory=list, description="Top 3 SHAP drivers in plain English")
    planet_radius: Optional[float] = None
    planet_mass: Optional[float] = None
    orbital_period: Optional[float] = None
    equilibrium_temperature: Optional[float] = None
    distance: Optional[float] = None
    stellar_name: Optional[str] = None
    hz_status: Optional[str] = None
    anomaly_score: Optional[float] = None
    is_jwst_target: Optional[bool] = None
    mass_is_estimated: Optional[bool] = None


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
    anomaly_score: List[Optional[float]] = Field(..., description="Anomaly scores")
    target_priority_score: List[Optional[float]] = Field(..., description="Heuristic scores")
    hz_status: List[str] = Field(..., description="Habitable zone statuses")
    explained_variance: List[float] = Field(..., description="PCA explained variance ratios")
    feature_names: List[str] = Field(..., description="Feature names used in PCA")


class WaterfallItem(BaseModel):
    feature: str = Field(..., description="Machine learning feature identifier")
    display_name: str = Field(..., description="Human-readable physical feature title")
    description: str = Field(..., description="Physical domain description")
    raw_value: str = Field(..., description="Formatted physical value with units")
    shap_value: float = Field(..., description="Linear SHAP contribution in log-odds margin space (Δ log-odds)")
    score_impact: float = Field(..., description="Calibrated priority score impact (points)")
    direction: str = Field(..., description="'positive' driver or 'negative' barrier")
    abs_importance: float = Field(..., description="Absolute Linear SHAP magnitude (|Δ log-odds|)")


class MathematicalInvariants(BaseModel):
    base_margin: float = Field(..., description="Global expected baseline margin (w0 in log-odds)")
    sum_shap_margin: float = Field(..., description="Sum of all individual feature SHAP contributions (sum phi_i)")
    predicted_margin: float = Field(..., description="Model predicted margin / final logit (sum phi_i + w0)")
    reconstruction_error: float = Field(
        ..., description="Residual reconstruction error (|sum(phi) + base - predicted|)"
    )


class PlanetExplanationResponse(BaseModel):
    planet_name: str = Field(..., description="Exoplanet identifier")
    ml_priority_score: float = Field(
        ..., ge=0.0, le=100.0, description="Score of the production model that is explained"
    )
    served_priority_score: Optional[float] = Field(
        None, description="Score the catalog serves for this planet (out-of-fold for planets labelled as JWST targets)"
    )
    explains_served_score: Optional[bool] = Field(
        None, description="True when the explained score is the served score (within 0.01)"
    )
    base_score: float = Field(..., ge=0.0, le=100.0, description="Expected baseline score across population")
    score_delta_from_base: float = Field(..., description="Net score shift attributed to planetary features")
    citation: str = Field("Lundberg & Lee (2017, NeurIPS)", description="Theoretical attribution framework citation")
    base_logit: Optional[float] = Field(None, description="Base value margin in log-odds units")
    final_logit: Optional[float] = Field(None, description="Final predicted logit margin in log-odds units")
    converted_percentile: Optional[float] = Field(
        None, description="100 x sigmoid(logit): a ranking score, neither a percentile nor a calibrated probability"
    )
    mathematical_invariants: MathematicalInvariants = Field(..., description="Linear SHAP additive conservation proof")
    top_positive_drivers: List[WaterfallItem] = Field(..., description="Top 5 features elevating priority")
    top_negative_barriers: List[WaterfallItem] = Field(..., description="Top 5 features lowering priority")
    full_waterfall: List[WaterfallItem] = Field(..., description="All feature contributions ordered by absolute impact")


class DifferentialWaterfallItem(BaseModel):
    feature: str = Field(..., description="Feature identifier")
    display_name: str = Field(..., description="Human-readable physical title")
    planet_a_value: str = Field(..., description="Target A formatted physical value")
    planet_b_value: str = Field(..., description="Target B formatted physical value")
    diff_shap: float = Field(..., description="Delta Linear SHAP (phi_A - phi_B)")
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


class MethodologyWeightsResponse(BaseModel):
    scoring_config: Dict[str, float] = Field(..., description="Raw weights dictionary from priority_scorer.py")
    weights: Dict[str, float] = Field(..., description="Normalized weight per scoring category (0.0 to 1.0)")
    percentages: Dict[str, int] = Field(..., description="Integer percentage weight per scoring category (0 to 100)")
    total_weight: float = Field(..., description="Sum of category weights")


def _clean_val(val: Any) -> Any:
    """The value, or None when pandas reports it missing (NaN, NaT, None)."""
    if pd.isna(val):
        return None
    return val


def _first_number(row: Mapping[str, Any], *keys: str) -> Optional[float]:
    """First present, non-NaN value. (`a or b` is wrong here: NaN is truthy and 0.0 is falsy.)"""
    for key in keys:
        val = row.get(key)
        if val is not None and pd.notna(val):
            return float(val)
    return None


def _is_ranked(row: Mapping[str, Any]) -> bool:
    """False only for planets the artifact marks as ineligible for transmission spectroscopy."""
    eligible = row.get("eligible_for_transmission")
    return eligible is None or pd.isna(eligible) or bool(eligible)


def _require_ranked(row: Mapping[str, Any], label: str) -> None:
    if not _is_ranked(row):
        reason = _clean_val(row.get("exclusion_reason")) or "ineligible"
        raise HTTPException(
            status_code=422,
            detail=f"{label} is not ranked (not eligible for transmission spectroscopy: {reason})",
        )


def _true_flag(row: Mapping[str, Any], *keys: str) -> bool:
    """True when any of the flags is set; missing and NaN count as not set."""
    return any(pd.notna(row.get(k)) and bool(row.get(k)) for k in keys)


def _parse_components(val: object) -> Dict[str, Any]:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = ast.literal_eval(val)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, SyntaxError):  # not a Python literal: no components
            return {}
    return {}


def _row_to_planet_response(row: pd.Series) -> PlanetResponse:
    """Convert a DataFrame row to PlanetResponse with unified One Score, One Rank."""
    # The model ranks transmission-eligible planets only. The artifact also stores model outputs for ineligible
    # (e.g. non-transiting) planets, up to 99.99; they are meaningless, so they are never served. The heuristic
    # score is a different quantity and is no substitute.
    ranked = _is_ranked(row)
    p_score = _first_number(row, "priority_score", "ml_priority_score") if ranked else None
    heuristic = _first_number(row, "target_priority_score", "heuristic_habitability_score")
    ml_r = int(row["ml_rank"]) if pd.notna(row.get("ml_rank")) else None
    p_rank = int(row["priority_rank"]) if pd.notna(row.get("priority_rank")) else ml_r

    heur_score = _first_number(row, "heuristic_habitability_score", "target_priority_score")

    return PlanetResponse(
        planet_name=row.get("planet_name", ""),
        priority_score=p_score,
        priority_rank=p_rank,
        heuristic_habitability_score=heur_score,
        target_priority_score=heuristic,
        ml_priority_score=_first_number(row, "ml_priority_score", "priority_score") if ranked else None,
        ml_rank=ml_r if ml_r is not None else p_rank,
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
        already_observed_jwst=_true_flag(row, "already_observed_jwst", "is_jwst_target")
        if pd.notna(row.get("already_observed_jwst")) or pd.notna(row.get("is_jwst_target"))
        else None,
        tsm=_clean_val(row.get("tsm")),
        tsm_threshold=_clean_val(row.get("tsm_threshold")),
        kempton_size_class=_clean_val(row.get("kempton_size_class")),
        percentile_rank=_clean_val(row.get("percentile_rank")) if ranked else None,
        percentile_rank_string=_clean_val(row.get("percentile_rank_string")) if ranked else None,
        oof_ml_rank=int(row["oof_ml_rank"]) if pd.notna(row.get("oof_ml_rank")) else None,
        oof_priority_score=_clean_val(row.get("oof_priority_score")),
        unobserved_rank=int(row["unobserved_rank"]) if pd.notna(row.get("unobserved_rank")) else None,
        is_jwst_target=_true_flag(row, "is_jwst_target", "already_observed_jwst"),
        mass_is_estimated=_mass_is_estimated(row),
        mass_source=_clean_val(row.get("mass_source")),
    )


def _mass_is_estimated(row: pd.Series) -> Optional[bool]:
    """True/False only when the artifact records mass provenance; None (unknown) otherwise.

    Older artifacts have no provenance column. Inferring "measured" from the presence of a mass was wrong:
    most archive masses for transiting planets are themselves estimates from a mass-radius relation.
    """
    value = row.get("mass_is_estimated")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return bool(value)


def _row_to_planet_detail_response(row: pd.Series) -> PlanetDetailResponse:
    """Detail response = the list response (single source of truth) plus detail-only fields."""
    base = _row_to_planet_response(row).model_dump()
    return PlanetDetailResponse(
        **base,
        priority_components=_parse_components(row.get("priority_components", {})),
        stellar_effective_temperature=_clean_val(row.get("stellar_effective_temperature")),
        stellar_radius=_clean_val(row.get("stellar_radius")),
        stellar_mass=_clean_val(row.get("stellar_mass")),
        stellar_metallicity=_clean_val(row.get("stellar_metallicity")),
        stellar_name=_clean_val(row.get("stellar_name")),
        semi_major_axis=_clean_val(row.get("semi_major_axis")),
        earth_similarity=_clean_val(row.get("earth_similarity")),
        observational_accessibility=_clean_val(row.get("observational_accessibility")),
        data_quality=_clean_val(row.get("data_quality")),
    )


@router.get("/planets", response_model=List[PlanetResponse])
def get_planets(
    limit: int = Query(100, ge=1, le=500, description="Maximum number of planets to return"),
    offset: int = Query(0, ge=0, le=1_000_000, description="Number of planets to skip"),
    min_priority: float = Query(0.0, ge=0.0, le=100.0, description="Minimum priority score filter"),
    max_priority: float = Query(100.0, ge=0.0, le=100.0, description="Maximum priority score filter"),
    q: Optional[str] = Query(None, max_length=100, description="Planet name substring (literal, no wildcards)"),
    hz_status: Optional[str] = Query(
        None, description="Filter by habitable zone status (Inside HZ, Near HZ, Outside HZ)"
    ),
    sort_by: str = Query(
        "priority",
        pattern="^(priority|heuristic|ml)$",
        description="Ranking scheme: 'priority' (default, Supervised ML) or 'heuristic'",
    ),
) -> List[PlanetResponse]:
    """
    Get list of exoplanets with priority scores via vectorized DuckDB engine.

    Executes parameterized SQL with predicate pushdown over Parquet storage.
    """
    if min_priority > max_priority:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"min_priority ({min_priority}) cannot be greater than max_priority ({max_priority})",
        )

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


@router.get("/planets/compare-explain", response_model=ComparisonExplanationResponse)
def get_comparison_explanation(
    planet_a: str = Query(..., description="Target name of first exoplanet"),
    planet_b: str = Query(..., description="Target name of second exoplanet"),
) -> Dict[str, Any]:
    """
    Differential Linear SHAP attribution: explains ranking differentials between two planets.

    Computes Delta_phi_i = phi_i(A) - phi_i(B) to isolate why Planet A ranks higher or lower than Planet B.
    """
    if not planet_a.strip() or not planet_b.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Both planet_a and planet_b must be non-empty strings"
        )

    engine = CatalogQueryEngine.get_instance()
    row_a = engine.get_planet_by_name(planet_a)
    if row_a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Planet A '{planet_a}' not found in catalog")

    row_b = engine.get_planet_by_name(planet_b)
    if row_b is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Planet B '{planet_b}' not found in catalog")

    _require_ranked(row_a, f"Planet A '{planet_a}'")
    _require_ranked(row_b, f"Planet B '{planet_b}'")
    explainer = SHAPExplainer.get_instance()
    return explainer.explain_comparison(row_a, row_b)


@router.get("/planets/{planet_name}/explain", response_model=PlanetExplanationResponse)
@router.get("/explain/{planet_name}", response_model=PlanetExplanationResponse)
def get_planet_explanation(planet_name: str) -> Dict[str, Any]:
    """
    Compute exact Linear SHAP feature attribution waterfall and ranking drivers for an individual exoplanet.

    Guarantees the mathematical conservation invariant: sum(phi_i) + base_margin = predicted_margin.
    """
    if not planet_name or len(planet_name.strip()) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Planet name cannot be empty")

    engine = CatalogQueryEngine.get_instance()
    planet_row = engine.get_planet_by_name(planet_name)

    if planet_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Planet '{planet_name}' not found in the dataset"
        )

    _require_ranked(planet_row, f"Planet '{planet_name}'")
    explainer = SHAPExplainer.get_instance()
    return explainer.explain_planet(planet_row)


@router.get("/planets/{planet_name}", response_model=PlanetDetailResponse)
def get_planet_details(planet_name: str) -> PlanetDetailResponse:
    """
    Get detailed information for a specific exoplanet via DuckDB.

    Case-insensitive exact match (hyphens and spaces are interchangeable).
    """
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
) -> List[PlanetResponse]:
    """
    Get top priority targets via vectorized DuckDB index scan.
    Main ranking defaults to unobserved candidate targets only.
    """
    engine = CatalogQueryEngine.get_instance()
    targets = engine.get_top_targets(
        limit=limit, min_priority=min_priority, sort_by=sort_by, exclude_observed=exclude_observed
    )
    return [_row_to_planet_response(t) for t in targets]


@router.get("/validation/known-targets", response_model=List[PlanetResponse])
def get_known_jwst_targets() -> List[PlanetResponse]:
    """
    Validation view: where planets labelled as JWST targets land, using out-of-fold ranks only.

    The labels are not human-verified (see reports/LABEL_REVIEW.md).
    """
    engine = CatalogQueryEngine.get_instance()
    planets = engine.get_known_jwst_targets()
    return [_row_to_planet_response(p) for p in planets]


@router.get("/recommendations", response_model=List[RecommendationResponse])
def get_recommendations(
    exclude_observed: bool = Query(True, description="Exclude planets already observed by JWST"),
    size_class: Optional[str] = Query(
        None, description="Filter by size class: terrestrial, small_sub_neptune, large_sub_neptune, gas_giant"
    ),
    limit: int = Query(25, ge=1, le=100, description="Maximum recommendations to return"),
    offset: int = Query(0, ge=0, le=1_000_000, description="Offset for pagination"),
) -> List[RecommendationResponse]:
    """
    Get prioritized target recommendations with plain-English scientific justifications.
    Filters out already-observed JWST targets by default and supports size class sub-filtering.
    """
    engine = CatalogQueryEngine.get_instance()
    planets = engine.get_recommendations(
        limit=limit, offset=offset, exclude_observed=exclude_observed, size_class=size_class
    )
    try:
        explainer: Optional[SHAPExplainer] = SHAPExplainer.get_instance()
    except ExplanationsUnavailable:
        explainer = None  # logged at startup; the recommendations are served without reasons
    from app.ml.explainability import get_plain_english_reasons_for_planet

    results = []
    for idx, p in enumerate(planets):
        known_rank = _first_number(p, "unobserved_rank", "priority_rank")
        rank = int(known_rank) if known_rank is not None else offset + idx + 1
        score = _first_number(p, "priority_score", "ml_priority_score")
        if score is None:
            continue  # eligible planets always have one; never substitute another quantity
        tsm_val = _clean_val(p.get("tsm"))
        thresh_val = _clean_val(p.get("tsm_threshold"))
        ratio = round(tsm_val / thresh_val, 2) if (tsm_val is not None and thresh_val and thresh_val > 0) else None

        # Generate top 3 SHAP drivers in plain English
        try:
            reasons = [] if explainer is None else get_plain_english_reasons_for_planet(p, explainer=explainer)
        except Exception:  # noqa: BLE001 - logged with traceback; the recommendation is still served
            # The recommendation stays useful without its reasons, but the failure must be visible.
            logger.warning("Explanation reasons unavailable for %s", p.get("planet_name"), exc_info=True)
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
                already_observed_jwst=_true_flag(p, "already_observed_jwst", "is_jwst_target"),
                reasons=reasons,
                planet_radius=_clean_val(p.get("planet_radius")),
                planet_mass=_clean_val(p.get("planet_mass")),
                orbital_period=_clean_val(p.get("orbital_period")),
                equilibrium_temperature=_clean_val(p.get("equilibrium_temperature")),
                distance=_clean_val(p.get("distance")),
                stellar_name=_clean_val(p.get("stellar_name")),
                hz_status=_clean_val(p.get("hz_status")),
                anomaly_score=_clean_val(p.get("anomaly_score")),
                is_jwst_target=_true_flag(p, "already_observed_jwst", "is_jwst_target"),
                mass_is_estimated=_mass_is_estimated(pd.Series(p)),
            )
        )
    return results


@router.get("/analysis", response_model=AnalysisResponse)
def get_analysis() -> AnalysisResponse:
    """
    Get overall analysis and population statistics via vectorized DuckDB aggregations.
    """
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


@router.get("/system/latency-benchmark", response_model=None)
def get_latency_benchmark(
    iterations: int = Query(100, ge=10, le=500, description="Number of query iterations to benchmark"),
) -> Dict[str, Any]:
    """
    Time a fixed set of in-process DuckDB queries, one after another (not an HTTP or concurrency measurement).
    """
    engine = CatalogQueryEngine.get_instance()
    return engine.benchmark_latency(iterations=iterations)


@router.get("/anomaly-pca", response_model=AnomalyPCAResponse)
def get_anomaly_pca() -> AnomalyPCAResponse:
    """
    Get PCA data for anomaly visualization from in-memory preloaded artifact.

    Returns 2D PCA projection of exoplanet features along with
    anomaly scores and other metadata for visualization.
    """
    engine = CatalogQueryEngine.get_instance()
    pca_data = engine.get_precomputed_pca()

    if "error" in pca_data:
        logger.warning(f"PCA error: {pca_data['error']}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=pca_data["error"])

    return AnomalyPCAResponse(**pca_data)


@router.get("/evaluation/benchmark", response_model=None)
def get_evaluation_benchmark(
    split: str = Query(
        "test",
        pattern="^(test|val)$",
        description="Dataset split to evaluate: 'test' (out-of-time >=2022) or 'val' (2018-2021)",
    ),
) -> Dict[str, Any]:
    """
    Get offline ML ranking evaluation benchmark leaderboard and metrics from in-memory artifact.

    The report compares ranking models and baselines against the artifact's JWST target labels. Those labels
    are NOT human-verified (see reports/LABEL_REVIEW.md), so every metric is provisional.
    """
    engine = CatalogQueryEngine.get_instance()
    report = engine.get_benchmark_report(split=split)
    if "error" in report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=report["error"])
    return report


@router.get("/models/ltr/info", response_model=None)
def get_ltr_info() -> Dict[str, Any]:
    """
    Get the supervised ranking model's metadata, hyperparameters and benchmarks from the artifact manifest.
    """
    engine = CatalogQueryEngine.get_instance()
    return engine.get_ltr_info()


@router.get("/models/ltr/feature-importance", response_model=None)
def get_ltr_feature_importance() -> Dict[str, Any]:
    """
    Get ranked feature importances for the supervised ranking model (for the logistic regression: standardized coefficients).
    """
    engine = CatalogQueryEngine.get_instance()
    return engine.get_ltr_feature_importances()


# ================================================================
# Model Registry Endpoints
# ================================================================


@router.get("/models/registry/versions", response_model=None)
def list_registered_versions() -> Dict[str, Any]:
    """
    List all model versions tracked in the Model Registry,
    including their deployment status, offline evaluation metrics, and registration date.
    """
    from app.ml.model_registry import ModelRegistry

    registry = ModelRegistry()
    active = registry.get_active_version()
    versions = registry.list_versions()
    return {"active_version": active, "total_versions": len(versions), "versions": versions}


@router.get("/models/registry/active", response_model=None)
def get_active_model_version() -> Dict[str, Any]:
    """
    Get full metadata, provenance, and SHA256 integrity checksums
    for the currently deployed production model.
    """
    from app.ml.model_registry import ModelRegistry

    registry = ModelRegistry()
    active_ver = registry.get_active_version()
    if not active_ver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active model version set in registry.")
    entry = registry.get_version(active_ver)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active version '{active_ver}' not found in registry index.",
        )
    # The build environment (host name, platform) is provenance for the repository, not for the public API.
    public = {k: v for k, v in entry.items() if k != "environment"}
    # Promotion is by deployment: the pipeline changes active_version.txt and the API serves the new version
    # after a restart. Report both, so a pointer the processes have not loaded yet is never shown as live.
    served = CatalogQueryEngine.get_instance().active_version
    public["active_version"] = active_ver
    public["served_version"] = served
    public["serving_matches_pointer"] = served == active_ver
    # Entries written before 2026-11-24 record the length of the top-10 list as n_features: count the served model's inputs.
    try:
        from app.ml.explainability import SHAPExplainer

        public["served_model_features"] = len(SHAPExplainer.get_instance().feature_names)
    except ExplanationsUnavailable:
        public["served_model_features"] = None  # the mismatch is reported by /ready and /metrics
    except Exception:
        logger.exception("Model registry: served model unavailable")
        public["served_model_features"] = None
    return public


@router.get("/models/registry/validate/{version}", response_model=None)
def validate_model_integrity(version: str) -> Dict[str, Any]:
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
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/models/registry/compare", response_model=None)
def compare_model_versions(
    version_a: str = Query(..., description="First version tag (candidate)"),
    version_b: str = Query(..., description="Second version tag (baseline)"),
) -> Dict[str, Any]:
    """
    Compare offline evaluation metrics (NDCG@10, MAP, PR-AUC), training configs,
    and dataset sizes between two registered model versions.
    """
    try:
        from app.ml.model_registry import ModelRegistry

        registry = ModelRegistry()
        comparison = registry.compare_versions(version_a, version_b)
        if "error" in comparison:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=comparison["error"])
        return comparison
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/methodology/weights", response_model=MethodologyWeightsResponse)
def get_methodology_weights() -> MethodologyWeightsResponse:
    """
    Retrieve domain astrophysical heuristic weighting formulation from priority_scorer.py config.
    """
    scorer = TargetPriorityScorer()
    config = scorer.scoring_config

    pr_w = float(config.get("planetary_relevance_weight", 0.35))
    oa_w = float(config.get("observational_accessibility_weight", 0.30))
    sc_w = float(config.get("stellar_characteristics_weight", 0.15))
    dq_w = float(config.get("data_quality_weight", 0.10))
    as_w = float(config.get("anomaly_score_weight", 0.10))

    weights = {
        "planetary_relevance": pr_w,
        "observational_accessibility": oa_w,
        "stellar_characteristics": sc_w,
        "data_quality": dq_w,
        "anomaly_score": as_w,
    }

    percentages = {
        "planetary_relevance": int(round(pr_w * 100)),
        "observational_accessibility": int(round(oa_w * 100)),
        "stellar_characteristics": int(round(sc_w * 100)),
        "data_quality": int(round(dq_w * 100)),
        "anomaly_score": int(round(as_w * 100)),
    }

    return MethodologyWeightsResponse(
        scoring_config=config,
        weights=weights,
        percentages=percentages,
        total_weight=round(sum(weights.values()), 4),
    )
