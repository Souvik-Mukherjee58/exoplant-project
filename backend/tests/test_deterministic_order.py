"""Every listing has a total order (improvement I-1).

Sort keys tie (planets without a rank, equal heuristic scores), and DuckDB returns tied rows in no fixed order,
so page 2 could repeat a planet of page 1 and skip another. The planet name, unique in the catalog, breaks ties.
"""

from typing import List

import pytest

from app.services.query_engine import CatalogQueryEngine

PAGE = 500


@pytest.fixture(scope="module")
def engine() -> CatalogQueryEngine:
    return CatalogQueryEngine.get_instance()


def _all_pages(engine: CatalogQueryEngine, sort_by: str) -> List[str]:
    names: List[str] = []
    offset = 0
    while True:
        rows = engine.query_planets(limit=PAGE, offset=offset, sort_by=sort_by)
        names += [r["planet_name"] for r in rows]
        if len(rows) < PAGE:
            return names
        offset += PAGE


def test_planet_names_are_unique(engine: CatalogQueryEngine) -> None:
    total, distinct = (
        engine.get_cursor().execute("SELECT COUNT(*), COUNT(DISTINCT planet_name) FROM planets").fetchone()
    )
    assert total == distinct


@pytest.mark.parametrize("sort_by", ["priority", "ml", "heuristic"])
def test_paging_returns_every_planet_once_in_a_stable_order(engine: CatalogQueryEngine, sort_by: str) -> None:
    first = _all_pages(engine, sort_by)
    assert len(first) == len(set(first)), "a planet appears on two pages"
    assert first == _all_pages(engine, sort_by)


def test_the_order_has_ties_that_the_name_breaks(engine: CatalogQueryEngine) -> None:
    """The case that needs the tie-breaker exists: ineligible planets share a NULL rank."""
    tied = engine.get_cursor().execute("SELECT COUNT(*) FROM planets WHERE priority_rank IS NULL").fetchone()[0]
    assert tied > 1
    names = _all_pages(engine, "priority")
    unranked = names[-tied:]
    assert unranked == sorted(unranked)


def test_breakdowns_have_a_fixed_order(engine: CatalogQueryEngine) -> None:
    stats = engine.get_analysis_stats()
    for key in ("hz_distribution", "discovery_method_distribution"):
        counts = list(stats[key].items())
        assert counts == sorted(counts, key=lambda kv: (-kv[1], kv[0])), key
