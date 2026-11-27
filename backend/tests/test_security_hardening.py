"""Security/reliability hardening: rate-limit client identity, memory bound, CORS validation, no model changes over HTTP.

SYNTHETIC TEST DATA: IP addresses are from documentation ranges (RFC 5737); no real clients.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, validate_cors_origins
from app.ml.model_registry import ModelRegistry
from app.observability import RateLimitingMiddleware


def _limited_app(limit: int, hops: int) -> TestClient:
    mini = FastAPI()
    mini.add_middleware(RateLimitingMiddleware, requests_per_minute=limit, trusted_proxy_hops=hops)

    @mini.get("/x")
    def x():
        return {"ok": True}

    return TestClient(mini)


def test_spoofed_x_forwarded_for_does_not_bypass_limit_by_default():
    client = _limited_app(limit=2, hops=0)
    codes = [client.get("/x", headers={"X-Forwarded-For": f"203.0.113.{i}"}).status_code for i in range(4)]
    assert codes == [200, 200, 429, 429]


def test_trusted_proxy_hop_uses_entry_appended_by_proxy():
    client = _limited_app(limit=1, hops=1)
    # The proxy appends the real client as the last entry; earlier entries are client-supplied.
    assert client.get("/x", headers={"X-Forwarded-For": "198.51.100.7, 192.0.2.1"}).status_code == 200
    assert client.get("/x", headers={"X-Forwarded-For": "198.51.100.8, 192.0.2.1"}).status_code == 429
    assert client.get("/x", headers={"X-Forwarded-For": "198.51.100.7, 192.0.2.2"}).status_code == 200


def test_rate_limit_reset_header_is_wall_clock_epoch():
    import time

    client = _limited_app(limit=1, hops=0)
    client.get("/x")
    resp = client.get("/x")
    assert resp.status_code == 429
    reset = int(resp.headers["X-RateLimit-Reset"])
    assert time.time() - 5 < reset <= time.time() + 61


def test_stale_clients_are_evicted_when_map_is_large(monkeypatch):
    mw = RateLimitingMiddleware(FastAPI(), requests_per_minute=10)
    mw._history = {f"192.0.2.{i}": [0.0] for i in range(50)}
    mw._history["198.51.100.1"] = [1_000_000.0]
    mw._evict_stale(cutoff=10.0)
    assert list(mw._history) == ["198.51.100.1"]


def test_cors_wildcard_subdomains_are_rejected():
    with pytest.raises(ValueError, match="wildcard subdomains"):
        validate_cors_origins(["https://*.vercel.app"])
    assert validate_cors_origins(["*"]) == ["*"]
    assert validate_cors_origins(["https://exosignal.vercel.app"]) == ["https://exosignal.vercel.app"]


def test_cors_preflight_allows_only_read_methods():
    client = TestClient(app)
    resp = client.options(
        "/api/v1/top-targets",
        headers={"Origin": "https://example.test", "Access-Control-Request-Method": "GET"},
    )
    assert resp.status_code == 200
    assert "POST" not in resp.headers.get("access-control-allow-methods", "")


def test_no_http_request_can_change_the_live_model(monkeypatch):
    """The admin gate is gone with the endpoints: no request, not even with the old admin token, changes the model.

    Promotion is by deployment (audit finding F-02; the registry itself is tested in test_model_promotion.py).
    """
    monkeypatch.setenv("ADMIN_TOKEN", "synthetic-test-token")
    calls = []
    monkeypatch.setattr(ModelRegistry, "promote", lambda self, *a, **k: calls.append(("promote", a)))
    monkeypatch.setattr(ModelRegistry, "rollback", lambda self, *a, **k: calls.append(("rollback", a)))
    client = TestClient(app)
    old_admin = {"Authorization": "Bearer synthetic-test-token"}

    assert not hasattr(Settings(), "ADMIN_TOKEN")  # the setting that once enabled the endpoints is not read
    assert client.post("/api/v1/models/registry/promote/v1_2026-10-29").status_code in (404, 405)
    assert client.post("/api/v1/models/registry/rollback").status_code in (404, 405)
    assert client.post("/api/v1/models/registry/promote/v1_2026-10-29", headers=old_admin).status_code in (404, 405)
    assert client.post("/api/v1/models/registry/rollback", headers=old_admin).status_code in (404, 405)
    assert calls == []  # no request reached the registry's promote or rollback
