"""Tests for vectorized DuckDB CatalogQueryEngine, concurrency, and API latency."""

import concurrent.futures

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.query_engine import CatalogQueryEngine


@pytest.fixture(scope="module")
def engine():
    """Get the DuckDB CatalogQueryEngine instance."""
    eng = CatalogQueryEngine.get_instance()
    assert eng.conn is not None
    return eng


# ---------------------------------------------------------------------------
# 1. Engine Initialization & Invariants
# ---------------------------------------------------------------------------


def test_query_engine_initialization(engine):
    assert engine.active_version is not None
    assert engine.parquet_path.exists()
    row_count = engine.conn.execute("SELECT COUNT(*) FROM planets").fetchone()[0]
    assert row_count > 6000, f"Engine must load complete catalog (got {row_count})"


def test_table_indexes_exist(engine):
    indexes = engine.conn.execute("""
        SELECT index_name FROM duckdb_indexes()
    """).fetchall()
    index_names = [r[0] for r in indexes]
    assert "idx_ml_priority" in index_names
    assert "idx_heuristic_priority" in index_names
    assert "idx_hz_status" in index_names


# ---------------------------------------------------------------------------
# 2. Parametric Querying & Filtering
# ---------------------------------------------------------------------------


def test_query_planets_pagination(engine):
    page1 = engine.query_planets(limit=5, offset=0, sort_by="heuristic")
    page2 = engine.query_planets(limit=5, offset=5, sort_by="heuristic")

    assert len(page1) == 5
    assert len(page2) == 5

    names_page1 = [p["planet_name"] for p in page1]
    names_page2 = [p["planet_name"] for p in page2]

    # Pages must be strictly disjoint
    assert set(names_page1).isdisjoint(set(names_page2))


def test_query_planets_priority_range_filter(engine):
    results = engine.query_planets(min_priority=75.0, max_priority=85.0, limit=50)
    assert len(results) > 0
    for p in results:
        score = p["target_priority_score"]
        assert 75.0 <= score <= 85.0, f"Score {score} outside [75, 85]"


def test_query_planets_hz_filter(engine):
    results = engine.query_planets(hz_status="Inside HZ", limit=30)
    assert len(results) > 0
    for p in results:
        assert p["hz_status"] == "Inside HZ"


def test_query_planets_substring_search(engine):
    results = engine.query_planets(q="trappist", limit=20)
    assert len(results) > 0
    for p in results:
        assert "trappist" in p["planet_name"].lower()


def test_query_planets_ml_sort(engine):
    results = engine.query_planets(limit=10, sort_by="ml")
    assert len(results) == 10
    scores = [p["ml_priority_score"] for p in results]
    # Verify sorted descending
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# 3. Exact Lookup & SQL Injection Defense
# ---------------------------------------------------------------------------


def test_get_planet_by_name_case_insensitive(engine):
    # Check mixed case
    p1 = engine.get_planet_by_name("tOI-700 D")
    assert p1 is not None
    assert p1["planet_name"] == "TOI-700 d"

    p2 = engine.get_planet_by_name("TRAPPIST-1 e")
    assert p2 is not None
    assert p2["planet_name"] == "TRAPPIST-1 e"

    # Nonexistent
    assert engine.get_planet_by_name("FakePlanet 9999 z") is None


def test_sql_injection_defense(engine):
    # Malicious injection payloads
    payloads = [
        "'; DROP TABLE planets; --",
        "' OR '1'='1",
        "1; SELECT * FROM planets",
        "UNION ALL SELECT * FROM planets--",
    ]
    for injection in payloads:
        results = engine.query_planets(q=injection, limit=10)
        assert isinstance(results, list)

    # Ensure table still intact
    count = engine.conn.execute("SELECT COUNT(*) FROM planets").fetchone()[0]
    assert count > 6000


# ---------------------------------------------------------------------------
# 4. Multi-Threaded Concurrency
# ---------------------------------------------------------------------------


def test_concurrent_threads_query_execution(engine):
    """Simulate 20 concurrent threads querying DuckDB simultaneously."""

    def worker_task(thread_id: int):
        q_term = "kepler" if thread_id % 2 == 0 else "toi"
        res = engine.query_planets(q=q_term, limit=10, sort_by="ml")
        return len(res)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker_task, i) for i in range(20)]
        results = [f.result() for f in futures]

    assert len(results) == 20
    assert all(r > 0 for r in results)


# ---------------------------------------------------------------------------
# 5. Statistical Aggregations & Latency Benchmark
# ---------------------------------------------------------------------------


def test_population_stats_aggregates(engine):
    stats = engine.get_analysis_stats()
    assert stats["total_planets"] > 6000
    assert stats["score_distribution"]["min"] <= stats["score_distribution"]["max"]
    assert len(stats["priority_histogram"]) == 5
    assert "Inside HZ" in stats["hz_distribution"]
    assert "Transit" in stats["discovery_method_distribution"]


def test_latency_benchmark(engine):
    bench = engine.benchmark_latency(iterations=50)
    assert bench["iterations"] == 50
    assert "DuckDB" in bench["engine"]
    assert bench["p50_ms"] < 10.0, f"P50 latency must be sub-10ms (got {bench['p50_ms']:.2f}ms)"


# ---------------------------------------------------------------------------
# 6. API Endpoints Contract
# ---------------------------------------------------------------------------


def test_api_latency_benchmark_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/system/latency-benchmark?iterations=20")
    assert response.status_code == 200
    data = response.json()
    assert "p50_ms" in data
    assert "DuckDB" in data["engine"]


def test_api_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "DuckDB" in data["query_engine"]
    assert data["catalog_records"] > 6000
