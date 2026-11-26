# ADR 0003: In-Process DuckDB & Columnar Parquet Over External PostgreSQL

- **Status**: Accepted (owner acceptance not recorded in the repository; see the revision below)
- **Date**: 2026-10-28
- **Deciders**: Souvik Mukherjee (project owner; solo project, drafted with AI coding assistants)

---

## Context & Problem Statement

ExoSignal serves analytical queries with low-latency reads over the archive catalog (6,451 planets in the current artifact ($N = 4,643$ transmission-eligible targets) with 40+ numerical physical parameters, machine learning ranking scores, and observational metrics.

Workload Characteristics:

- **Read-Heavy / Analytical**: Endpoints filter on continuous physical bounds (`min_priority`, `hz_status`, `radius`, `distance`), perform multi-key ordering, and execute single-target point lookups.
- **Data Updates per Release**: Catalog updates occur offline when a new version artifact is built by the data pipeline, not via continuous OLTP row inserts.
- **Resource Constraints**: Free-tier cloud deployments (Render, Fly.io) provide 512–1024 MB RAM without dedicated managed database instances.

---

## Decision

We use an **in-process DuckDB engine querying immutable, versioned Parquet storage (`artifacts/{version}/planets.parquet`)** coupled with startup memory preloading:

1. **No External Database Container**: DuckDB runs embedded inside the Python backend process, eliminating external TCP sockets, database connection pools, authentication overhead, and network round-trip latency.
2. **Columnar Predicate Pushdown**: DuckDB compiles vectorized SQL queries with projection pruning, reading only the requested columns directly from memory-mapped Parquet structures.
3. **Startup Preloading**: All JSON metadata, PCA projections, and DuckDB catalog indexes load once during the FastAPI application `lifespan` startup. Hot request paths perform **zero disk I/O**.
4. **Immutable Versioning**: Artifact versions are self-contained folders with a cryptographic manifest. Upgrading or rolling back a catalog version is an atomic pointer swap (`active_version.txt`) without SQL schema migrations.

---

## Performance comparison (correction, 2026-11-22)

An earlier version of this ADR showed a latency table comparing DuckDB with PostgreSQL (p50/p95, memory).
Those numbers were never measured: there is no PostgreSQL setup in this repository. They were removed.
Measured latency comes only from `reports/LOADTEST.md` (k6) and the capacity curve, with hardware stated.
The decision itself rests on the qualitative points above: a read-only catalog of a few thousand rows that
changes only when a new artifact ships needs no database server.

## Consequences

### Positive

- No database network hop on the read path (latency to be measured; see reports/LOADTEST.md).
- Docker containers run completely self-contained with no external dependencies.
- Rollbacks and canary promotions operate atomically via filesystem pointers.

### Negative / Trade-offs

- DuckDB does not support concurrent write transactions across multiple distributed nodes (acceptable for an immutable, read-only analytical catalog).

## Revision 2026-11-24 (correction)

The text above is kept as written. Corrections:

- **Status.** "Accepted" has no recorded evidence of owner acceptance (no review, sign-off or approval is in git). It is
  to be read as "implemented".
- **"Zero disk I/O", "memory-mapped".** The catalog is loaded into an in-memory table at startup.
