"""Load-test tooling: k6 summary parsing, SLO knee, rate-limit preflight, Docker URL mapping.

SYNTHETIC TEST DATA: the k6 summaries below are made up to exercise the parsing; they are not measurements.
"""

import importlib
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

capacity = importlib.import_module("run_capacity_curve")
render = importlib.import_module("render_loadtest_report")


def _summary(rate, p95, err, dropped=0):
    return {
        "metrics": {
            "http_req_duration": {"med": p95 / 3, "p(95)": p95, "p(99)": p95 * 1.5, "max": p95 * 3},
            "http_reqs": {"count": rate * 60, "rate": rate * 0.999},
            "http_req_failed": {"passes": 0, "fails": rate * 60, "value": err},
            "dropped_iterations": {"count": dropped},
        }
    }


def test_stage_from_summary_reads_k6_summary_export():
    s = capacity.stage_from_summary(100, _summary(100, 120.0, 0.002))
    assert s["target_rate_rps"] == 100
    assert s["p95_ms"] == 120.0
    assert s["p99_ms"] == pytest.approx(180.0)
    assert s["error_rate"] == 0.002
    assert s["achieved_rps"] == pytest.approx(99.9)


def test_capacity_section_reports_highest_rate_meeting_slo():
    stages = [
        capacity.stage_from_summary(50, _summary(50, 40.0, 0.0)),
        capacity.stage_from_summary(100, _summary(100, 90.0, 0.0)),
        capacity.stage_from_summary(200, _summary(200, 400.0, 0.0)),  # p95 over SLO
        capacity.stage_from_summary(400, _summary(400, 90.0, 0.2)),  # errors over SLO
    ]
    md = render.capacity_section(
        {"kind": "capacity_curve", "hardware": "SYNTHETIC", "client_location": "SYNTHETIC", "stages": stages}
    )
    assert "Highest measured rate meeting the SLO: 100 req/s" in md
    assert md.count("| yes |") == 2 and md.count("| no |") == 2


def test_capacity_section_when_nothing_meets_slo():
    stages = [capacity.stage_from_summary(50, _summary(50, 900.0, 0.0))]
    md = render.capacity_section({"kind": "capacity_curve", "stages": stages})
    assert "No measured rate met the SLO" in md


def test_preflight_aborts_when_rate_limit_would_throttle(monkeypatch):
    class FakeResp:
        headers = {"X-RateLimit-Limit": "120"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(capacity.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    msg = capacity.preflight("http://synthetic.invalid", max_rate=100)
    assert msg is not None and "RATE_LIMIT_PER_MINUTE=0" in msg

    FakeResp.headers = {}
    assert capacity.preflight("http://synthetic.invalid", max_rate=100) is None


def test_docker_url_maps_localhost_only():
    assert capacity.docker_url("http://localhost:8000") == "http://host.docker.internal:8000"
    assert capacity.docker_url("http://127.0.0.1:8000") == "http://host.docker.internal:8000"
    assert capacity.docker_url("https://exosignal.fly.dev") == "https://exosignal.fly.dev"


def test_render_requires_hardware_for_measured_data():
    # The old default claimed hardware nobody had checked ("16 logical cores, 32GB RAM").
    import inspect

    src = inspect.getsource(render.main)
    assert "16 logical cores" not in src
    assert "--hardware is required" in src
