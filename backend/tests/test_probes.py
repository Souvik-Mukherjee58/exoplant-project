"""Health, readiness and metrics probes (audit finding F-06).

The probes query DuckDB and read files. As `async def` they ran that blocking work on the event loop, so one
slow probe delayed every other request. As plain `def` FastAPI runs them in its thread pool.
"""

import asyncio
import inspect
import time
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.query_engine import CatalogQueryEngine

client = TestClient(app)


class _SlowEngine:
    """A stand-in engine whose COUNT(*) takes `delay` seconds and returns `count`."""

    active_version = "v_test"

    def __init__(self, delay: float = 0.0, count: int = 10, conn: Any = object()) -> None:
        self.delay, self.count, self.conn = delay, count, conn

    def count_records(self) -> int:
        time.sleep(self.delay)
        return self.count

    def get_cursor(self) -> "_SlowEngine":
        return self

    def execute(self, sql: str) -> "_SlowEngine":
        time.sleep(self.delay)
        return self

    def fetchone(self) -> tuple:
        return (self.count,)


@pytest.mark.parametrize("probe", [main.health, main.ready, main.metrics])
def test_probes_are_synchronous_so_fastapi_runs_them_in_its_thread_pool(probe: Any) -> None:
    assert not inspect.iscoroutinefunction(probe)


def test_a_slow_probe_does_not_block_other_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CatalogQueryEngine, "get_instance", classmethod(lambda cls, *a, **k: _SlowEngine(delay=1.0)))

    async def scenario() -> float:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            slow = asyncio.create_task(ac.get("/ready"))
            await asyncio.sleep(0.05)  # the probe is now waiting on the "database"
            start = time.perf_counter()
            fast = await ac.get("/")
            elapsed = time.perf_counter() - start
            assert fast.status_code == 200
            assert (await slow).status_code == 200
            return elapsed

    assert asyncio.run(scenario()) < 0.5  # with an async probe it would wait for the full second


def test_health_reports_degraded_when_the_engine_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(cls: Any, *a: Any, **k: Any) -> Any:
        raise RuntimeError("engine down")

    monkeypatch.setattr(CatalogQueryEngine, "get_instance", classmethod(broken))
    body = client.get("/health").json()
    assert body["status"] == "degraded"
    assert "engine down" not in str(body)  # no internal detail leaks to the client
    assert client.get("/ready").status_code == 503
    assert client.get("/metrics").json()["subsystems"]["duckdb"] == {"status": "error"}


def test_ready_is_not_ready_without_a_connection_or_without_records(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CatalogQueryEngine, "get_instance", classmethod(lambda cls, *a, **k: _SlowEngine(conn=None)))
    assert client.get("/ready").status_code == 503
    monkeypatch.setattr(CatalogQueryEngine, "get_instance", classmethod(lambda cls, *a, **k: _SlowEngine(count=0)))
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
