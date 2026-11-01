"""Pytest configuration for backend test suite.

Points JWST_TARGETS_PATH to the verified test fixture so that algorithmic unit
tests (evaluation protocols, cross-validation, LTR model fitting, schema checks)
execute deterministically against known ground truth while the live reference catalog
(backend/data/reference/jwst_transmission_targets.csv) remains in its unreviewed state.
"""

import os
from pathlib import Path

# Configure fixture reference before importing app modules
_fixture_ref = Path(__file__).resolve().parent / "fixtures" / "fixture_jwst_reference.csv"
if _fixture_ref.exists():
    os.environ["JWST_TARGETS_PATH"] = str(_fixture_ref)

from app.config import settings  # noqa: E402
from app.ml import ground_truth  # noqa: E402

if _fixture_ref.exists():
    settings.JWST_TARGETS_PATH = _fixture_ref
    ground_truth.CONFIRMED_JWST_ATMOSPHERIC_TARGETS = ground_truth.get_verified_jwst_targets()
