"""SHAP-based local explainability and feature attribution engine for ExoSignal.

Implements TreeSHAP (Lundberg et al., Nature Machine Intelligence 2020) for local model interpretability:
1. Exact TreeSHAP feature attributions via LightGBM's native C++ implementation (pred_contrib=True).
2. Additive feature attribution guarantees: sum(SHAP) + Base Value = Predicted Margin.
3. Calibrated score-space decomposition into positive drivers and negative barriers.
4. Pairwise differential attribution explaining ranking reversals between any two planets.
5. Human-readable physical labels and unit formatting.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.ml.ltr_model import ExoSignalLTRModel

FEATURE_METADATA: Dict[str, Dict[str, str]] = {
    "transmission_snr_proxy": {
        "display_name": "Transmission Spectroscopic SNR",
        "description": "Composite observational signal-to-noise ratio for transit spectroscopy",
        "unit": "SNR index",
    },
    "planet_radius": {
        "display_name": "Planetary Radius",
        "description": "Physical radius of the planet relative to Earth",
        "unit": "R⊕",
    },
    "k_magnitude": {
        "display_name": "2MASS K-band Brightness",
        "description": "Infrared stellar apparent magnitude (lower = brighter host star)",
        "unit": "mag",
    },
    "j_magnitude": {
        "display_name": "2MASS J-band Brightness",
        "description": "Near-infrared stellar apparent magnitude",
        "unit": "mag",
    },
    "bulk_density_proxy": {
        "display_name": "Planetary Bulk Density",
        "description": "Mean density proxy (M / R^3) governing atmospheric retention",
        "unit": "ρ⊕",
    },
    "planet_mass": {
        "display_name": "Planetary Mass",
        "description": "Total mass (measured via RV/TTV or estimated via Chen & Kipping)",
        "unit": "M⊕",
    },
    "stellar_radius": {
        "display_name": "Stellar Host Radius",
        "description": "Radius of host star (smaller stars amplify transit depth)",
        "unit": "R☉",
    },
    "distance": {
        "display_name": "System Distance",
        "description": "Distance to planetary system from Earth",
        "unit": "pc",
    },
    "transit_depth_proxy": {
        "display_name": "Geometric Transit Depth",
        "description": "(R_p / R_*)^2 fractional transit dip amplitude",
        "unit": "ratio",
    },
    "scale_height_proxy": {
        "display_name": "Atmospheric Scale Height",
        "description": "Characteristic atmospheric thickness (T_eq * R^2 / M)",
        "unit": "km index",
    },
    "insolation_flux": {
        "display_name": "Insolation Flux",
        "description": "Stellar radiative flux incident on planet relative to Solar constant",
        "unit": "S⊕",
    },
    "distance_attenuation": {
        "display_name": "Proximity Factor",
        "description": "Geometric signal accessibility scaling with 1 / (1 + d / 100)",
        "unit": "factor",
    },
    "infrared_brightness_proxy": {
        "display_name": "Infrared Photon Flux",
        "description": "Direct photon collection efficiency in 2MASS infrared band",
        "unit": "flux index",
    },
    "earth_similarity": {
        "display_name": "Earth Similarity Index (ESI)",
        "description": "Published similarity to Earth physical parameters (Schulze-Makuch 2011)",
        "unit": "0-1 index",
    },
    "hz_proximity_score": {
        "display_name": "Habitable Zone Proximity",
        "description": "Continuous alignment with Kopparapu et al. insolation boundaries",
        "unit": "HZ score",
    },
    "orbital_period": {
        "display_name": "Orbital Period",
        "description": "Time to complete one orbit around host star",
        "unit": "days",
    },
    "semi_major_axis": {
        "display_name": "Semi-Major Axis",
        "description": "Average orbital distance from host star",
        "unit": "AU",
    },
    "equilibrium_temperature": {
        "display_name": "Equilibrium Temperature",
        "description": "Estimated planetary blackbody temperature under stellar illumination",
        "unit": "K",
    },
    "stellar_effective_temperature": {
        "display_name": "Stellar Teff",
        "description": "Effective surface temperature of the host star",
        "unit": "K",
    },
    "stellar_mass": {
        "display_name": "Stellar Host Mass",
        "description": "Mass of host star relative to the Sun",
        "unit": "M☉",
    },
    "stellar_metallicity": {
        "display_name": "Stellar Metallicity",
        "description": "[Fe/H] iron-to-hydrogen ratio of the host star",
        "unit": "dex",
    },
}

PLAIN_ENGLISH_TEMPLATES = {
    "distance": lambda val: (
        f"Nearby planetary system at {val} minimizes atmospheric photon attenuation"
        if val and val != "N/A"
        else "Close proximity to Earth minimizes atmospheric photon attenuation"
    ),
    "stellar_radius": lambda val: (
        f"Compact host star ({val}) amplifies transit depth and spectroscopic SNR"
        if val and val != "N/A"
        else "Compact host star amplifies transit depth and spectroscopic SNR"
    ),
    "scale_height_proxy": lambda val: (
        f"Extensive atmospheric scale height ({val}) enhances transmission feature amplitude"
        if val and val != "N/A"
        else "Extensive atmospheric scale height enhances transmission feature amplitude"
    ),
    "transit_depth_proxy": lambda val: (
        f"Deep transit geometry ({val}) produces prominent atmospheric absorption signal"
        if val and val != "N/A"
        else "Deep transit geometry produces prominent atmospheric absorption signal"
    ),
    "planet_radius": lambda val: (
        f"Favorable planetary radius ({val}) for transmission spectroscopy"
        if val and val != "N/A"
        else "Favorable planetary radius for transmission spectroscopy"
    ),
    "planet_mass": lambda val: (
        f"Low planetary bulk density allows extended, puffy atmospheric envelope ({val})"
        if val and val != "N/A"
        else "Low planetary bulk density allows extended, puffy atmospheric envelope"
    ),
    "semi_major_axis": lambda val: (
        f"Close-in orbit ({val}) yields high geometric transit probability"
        if val and val != "N/A"
        else "Close-in orbit yields high geometric transit probability"
    ),
    "orbital_period": lambda val: (
        f"Short orbital period ({val}) enables rapid transit observation stacking"
        if val and val != "N/A"
        else "Short orbital period enables rapid transit observation stacking"
    ),
    "equilibrium_temperature": lambda val: (
        f"Equilibrium temperature ({val}) provides high thermal scale height without extreme photochemical haze"
        if val and val != "N/A"
        else "Favorable equilibrium temperature provides high thermal scale height"
    ),
    "transmission_snr_proxy": lambda val: (
        "High predicted transmission SNR index indicates excellent spectroscopic accessibility"
    ),
    "infrared_brightness_proxy": lambda val: (
        "Bright infrared host magnitude provides strong photon throughput for NIRSpec/MIRI"
    ),
    "distance_attenuation": lambda val: "Close proximity to Earth enhances photon collection efficiency",
    "hz_proximity_score": lambda val: "Orbit lies within or near the circumstellar habitable zone",
    "earth_similarity": lambda val: (
        f"High Earth Similarity Index ({val}) marks a prime terrestrial atmospheric analog"
        if val and val != "N/A"
        else "High Earth Similarity Index marks a prime terrestrial atmospheric analog"
    ),
}


def format_plain_english_reason(feature: str, display_name: str, raw_value: str) -> str:
    template_fn = PLAIN_ENGLISH_TEMPLATES.get(feature)
    if template_fn:
        try:
            return template_fn(raw_value)
        except Exception:
            pass
    return f"{display_name} ({raw_value}) is a primary positive driver for spectroscopic follow-up"


def get_plain_english_reasons_for_planet(
    planet_data: Dict[str, Any], explainer: Optional["SHAPExplainer"] = None
) -> List[str]:
    """Extract top 3 plain English SHAP reasons for why a planet was prioritized."""
    if explainer is None:
        explainer = SHAPExplainer.get_instance()
    res = explainer.explain_planet(planet_data)
    return res.get("reasons", [])


class SHAPExplainer:
    """
    Computes exact instance-level TreeSHAP feature attributions and waterfall breakdowns.
    """

    _instance: Optional["SHAPExplainer"] = None

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or self._resolve_model_path()
        self.ltr_model = ExoSignalLTRModel.load(str(self.model_path))
        self.feature_names = self.ltr_model.feature_extractor.feature_names

    @classmethod
    def get_instance(cls, model_path: Optional[str] = None) -> "SHAPExplainer":
        """Singleton accessor for the SHAP explainer."""
        if cls._instance is None:
            cls._instance = cls(model_path=model_path)
        return cls._instance

    def _resolve_model_path(self) -> Path:
        """Find the active versioned LTR model artifact."""
        if Path("artifacts").exists():
            artifacts_dir = Path("artifacts")
        elif Path("backend/artifacts").exists():
            artifacts_dir = Path("backend/artifacts")
        else:
            artifacts_dir = Path("artifacts")

        active_ptr = artifacts_dir / "active_version.txt"
        if active_ptr.exists():
            version = active_ptr.read_text().strip()
            candidate = artifacts_dir / version / "ltr_model.joblib"
            if candidate.exists():
                return candidate

        candidates = list(artifacts_dir.glob("*/ltr_model.joblib"))
        if candidates:
            return sorted(candidates, key=lambda p: p.parent.name, reverse=True)[0]

        raise FileNotFoundError(f"No LTR model artifact found in {artifacts_dir}")

    def _format_raw_value(self, feature: str, val: Any) -> str:
        """Format raw physical feature value with appropriate physical unit."""
        if val is None or pd.isna(val):
            return "N/A"
        try:
            num = float(val)
        except (ValueError, TypeError):
            return str(val)

        meta = FEATURE_METADATA.get(feature, {})
        unit = meta.get("unit", "")

        if "magnitude" in feature:
            return f"{num:.2f} mag"
        if "radius" in feature:
            return f"{num:.2f} {unit}"
        if "mass" in feature:
            return f"{num:.2f} {unit}"
        if "temperature" in feature or "teff" in feature:
            return f"{num:.0f} K"
        if "period" in feature:
            return f"{num:.2f} d"
        if "distance" in feature and "attenuation" not in feature:
            return f"{num:.1f} pc"
        if "semi_major" in feature:
            return f"{num:.3f} AU"
        if "proxy" in feature or "factor" in feature:
            return f"{num:.3f}"
        return f"{num:.2f} {unit}".strip()

    def explain_planet(self, planet_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute TreeSHAP feature attributions and waterfall breakdown for a single planet.

        Args:
            planet_data: Dictionary of planet attributes

        Returns:
            Structured explanation dictionary with waterfall items, positive drivers, and barriers.
        """
        if hasattr(planet_data, "to_dict"):
            planet_dict = planet_data.to_dict()
        elif isinstance(planet_data, dict):
            planet_dict = planet_data
        else:
            planet_dict = dict(planet_data)

        if hasattr(self.ltr_model.feature_extractor, "extract_single"):
            X, raw_features = self.ltr_model.feature_extractor.extract_single(planet_dict)
        else:
            df_row = pd.DataFrame([planet_dict])
            raw_feats_df = self.ltr_model.feature_extractor._extract_raw_features(df_row)
            imputed_feats = raw_feats_df.fillna(self.ltr_model.feature_extractor.median_impute_values).fillna(0.0)
            if getattr(self.ltr_model.feature_extractor, "use_log_transform", False):
                imputed_feats = self.ltr_model.feature_extractor._apply_log_transform(imputed_feats)
            X = self.ltr_model.feature_extractor.scaler.transform(imputed_feats)
            raw_features = raw_feats_df.iloc[0].to_dict()

        if getattr(self.ltr_model, "model_type", "lightgbm") == "logistic":
            # Exact Linear SHAP: phi_i = w_i * (x_i - mean_i)
            shap_values, base_value_raw, predicted_margin = self.ltr_model.get_linear_shap(X[0])
        else:
            # Native LightGBM TreeSHAP: shape (1, n_features + 1)
            contribs = self.ltr_model.model.booster_.predict(X, pred_contrib=True)[0]
            shap_values = contribs[:-1]
            base_value_raw = float(contribs[-1])
            predicted_margin = float(np.sum(shap_values) + base_value_raw)

        # Calibrated 0-100 scores derived directly from logit margin
        raw_prob = 1.0 / (1.0 + np.exp(-predicted_margin))
        calibrated_score = round(float(np.clip(raw_prob * 100.0, 0.0, 100.0)), 1)
        base_prob = 1.0 / (1.0 + np.exp(-base_value_raw))
        base_score = round(float(np.clip(base_prob * 100.0, 0.0, 100.0)), 1)

        # Raw features map prepared during extraction
        scale_factor = (calibrated_score - base_score) / (
            np.sum(shap_values) if abs(np.sum(shap_values)) > 1e-6 else 1.0
        )

        waterfall_items: List[Dict[str, Any]] = []
        for i, feat in enumerate(self.feature_names):
            phi = float(shap_values[i])
            meta = FEATURE_METADATA.get(feat, {"display_name": feat.replace("_", " ").title(), "description": ""})
            raw_val = raw_features.get(feat)

            # Impact in calibrated score units
            score_impact = round(phi * scale_factor, 1)

            if phi >= 0:
                direction = "positive"
                phi_rounded = round(phi, 4)
                if phi_rounded <= 0:
                    phi_rounded = 0.0001
            else:
                direction = "negative"
                phi_rounded = round(phi, 4)
                if phi_rounded >= 0:
                    phi_rounded = -0.0001

            waterfall_items.append(
                {
                    "feature": feat,
                    "display_name": meta["display_name"],
                    "description": meta.get("description", ""),
                    "raw_value": self._format_raw_value(feat, raw_val),
                    "shap_value": phi_rounded,
                    "score_impact": score_impact,
                    "direction": direction,
                    "abs_importance": abs(phi),
                }
            )

        # Sort by absolute SHAP impact
        waterfall_items.sort(key=lambda x: float(x["abs_importance"]), reverse=True)

        positive_drivers = [
            item for item in waterfall_items if item["direction"] == "positive" and float(item["shap_value"]) > 0
        ][:5]
        negative_barriers = [
            item for item in waterfall_items if item["direction"] == "negative" and float(item["shap_value"]) < 0
        ][:5]

        # Generate top 3 plain-English reasons for target prioritization
        reasons = [
            format_plain_english_reason(str(d["feature"]), str(d["display_name"]), str(d["raw_value"]))
            for d in positive_drivers[:3]
        ]

        return {
            "planet_name": planet_data.get("planet_name", "Target"),
            "ml_priority_score": calibrated_score,
            "base_score": base_score,
            "score_delta_from_base": round(calibrated_score - base_score, 1),
            "mathematical_invariants": {
                "base_margin": round(base_value_raw, 6),
                "sum_shap_margin": round(float(np.sum(shap_values)), 6),
                "predicted_margin": round(predicted_margin, 6),
                "reconstruction_error": float(abs(np.sum(shap_values) + base_value_raw - predicted_margin)),
            },
            "top_positive_drivers": positive_drivers,
            "top_negative_barriers": negative_barriers,
            "reasons": reasons,
            "full_waterfall": waterfall_items,
        }

    def explain_comparison(self, planet_a_data: Dict[str, Any], planet_b_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Explain the ranking delta between two planets using differential TreeSHAP attributions:
        Delta_phi_i = phi_i(A) - phi_i(B).

        Identifies the exact physical drivers explaining why Planet A is ranked higher than Planet B.
        """
        expl_a = self.explain_planet(planet_a_data)
        expl_b = self.explain_planet(planet_b_data)

        shap_a = {item["feature"]: item for item in expl_a["full_waterfall"]}
        shap_b = {item["feature"]: item for item in expl_b["full_waterfall"]}

        diff_items = []
        for feat in self.feature_names:
            item_a = shap_a[feat]
            item_b = shap_b[feat]
            diff_shap = round(item_a["shap_value"] - item_b["shap_value"], 4)
            diff_score = round(item_a["score_impact"] - item_b["score_impact"], 1)

            diff_items.append(
                {
                    "feature": feat,
                    "display_name": item_a["display_name"],
                    "planet_a_value": item_a["raw_value"],
                    "planet_b_value": item_b["raw_value"],
                    "diff_shap": diff_shap,
                    "diff_score_impact": diff_score,
                    "advantage": "Planet A" if diff_shap > 0 else "Planet B",
                    "abs_diff": abs(diff_shap),
                }
            )

        diff_items.sort(key=lambda x: x["abs_diff"], reverse=True)

        return {
            "planet_a": expl_a["planet_name"],
            "planet_b": expl_b["planet_name"],
            "planet_a_score": expl_a["ml_priority_score"],
            "planet_b_score": expl_b["ml_priority_score"],
            "score_advantage": round(expl_a["ml_priority_score"] - expl_b["ml_priority_score"], 1),
            "primary_drivers_for_advantage": [item for item in diff_items if item["advantage"] == "Planet A"][:5],
            "primary_drivers_for_disadvantage": [item for item in diff_items if item["advantage"] == "Planet B"][:5],
            "differential_waterfall": diff_items,
        }
