"""The API finds its artifacts wherever it is started, and reports one version (improvement I-2).

The engine, registry, explainer and model loader each guessed the directory from the working directory
("artifacts", else "backend/artifacts"), so a stray artifacts/ folder where the server started won.
"""

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import APP_VERSION, resolve_artifacts_dir, settings
from app.main import app

BACKEND = Path(__file__).resolve().parents[1]


def test_the_default_is_the_backend_artifacts_directory() -> None:
    assert resolve_artifacts_dir() == BACKEND / "artifacts"


def test_an_explicit_directory_is_kept(tmp_path: Path) -> None:
    assert resolve_artifacts_dir(tmp_path) == tmp_path
    assert resolve_artifacts_dir("artifacts") in (Path("artifacts"), BACKEND / "artifacts")


def test_a_relative_setting_is_relative_to_the_backend() -> None:
    assert settings.get_artifacts_dir() == settings.BASE_DIR / "artifacts"


def test_a_decoy_artifacts_folder_in_the_working_directory_is_ignored(tmp_path: Path) -> None:
    decoy = tmp_path / "artifacts"
    decoy.mkdir()
    (decoy / "active_version.txt").write_text("v_decoy")
    script = (
        "import json\n"
        "from app.services.query_engine import CatalogQueryEngine\n"
        "from app.ml.model_registry import ModelRegistry\n"
        "from app.ml.explainability import SHAPExplainer\n"
        "e = CatalogQueryEngine.get_instance()\n"
        "print(json.dumps({'engine': str(e.artifacts_dir), 'version': e.active_version,\n"
        "  'registry': str(ModelRegistry().artifacts_dir), 'model': str(SHAPExplainer.get_instance().model_path)}))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={**__import__("os").environ, "PYTHONPATH": str(BACKEND)},
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    found = json.loads(out.stdout.strip().splitlines()[-1])
    assert Path(found["engine"]) == Path(found["registry"]) == BACKEND / "artifacts"
    assert found["version"] != "v_decoy"
    assert Path(found["model"]).is_relative_to(BACKEND / "artifacts")


def test_every_endpoint_reports_the_same_version() -> None:
    client = TestClient(app)
    assert app.version == APP_VERSION
    for path in ("/", "/health", "/metrics"):
        assert client.get(path).json()["version"] == APP_VERSION, path
