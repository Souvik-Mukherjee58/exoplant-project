import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { productionMetrics } from '../pages/Home';

// Checks against the repository's real files instead of hand-written mocks.
const root = resolve(__dirname, '../../..');

describe('contract with the backend', () => {
  it('reads the metrics of the served report', () => {
    const artifacts = resolve(root, 'backend/artifacts');
    const version = readFileSync(resolve(artifacts, 'active_version.txt'), 'utf-8').trim();
    const report = JSON.parse(
      readFileSync(resolve(artifacts, version, 'benchmark_report.json'), 'utf-8')
    );
    const metrics = productionMetrics(report);
    for (const [name, value] of Object.entries(metrics)) {
      expect(value, name).not.toBeNull();
    }
    expect(metrics.ap).toBeCloseTo(report.selected_production_model.mean_ap, 4);
    expect(productionMetrics({ ...report, leaderboard: [] }).ap).toBe(metrics.ap);
    expect(productionMetrics({})).toBeNull();
  });

  it('reads only latency fields that the API sends', () => {
    const engine = readFileSync(resolve(root, 'backend/app/services/query_engine.py'), 'utf-8');
    const body = engine.slice(engine.indexOf('def benchmark_latency'));
    const sent = [...body.slice(0, body.indexOf('    def close')).matchAll(/"(\w+)":/g)].map(
      (m) => m[1]
    );
    const page = readFileSync(resolve(__dirname, '../pages/ModelRegistry.jsx'), 'utf-8');
    const read = [...page.matchAll(/latencyBench\.(\w+)/g)].map((m) => m[1]);
    expect(read).toContain('p50_ms');
    expect(read.filter((field) => !sent.includes(field))).toEqual([]);
  });

  it('never asks for more rows than the API allows', () => {
    const api = readFileSync(resolve(root, 'backend/app/api/v1.py'), 'utf-8');
    const max = Number(
      api.match(/def get_planets\([\s\S]*?limit: int = Query\(100, ge=1, le=(\d+)/)[1]
    );
    const pages = resolve(__dirname, '../pages');
    const asked = readdirSync(pages).flatMap((f) =>
      [...readFileSync(resolve(pages, f), 'utf-8').matchAll(/(?:limit: |MAX_ROWS = )(\d+)/g)].map(
        (m) => Number(m[1])
      )
    );
    expect(asked.length).toBeGreaterThan(0);
    expect(Math.max(...asked)).toBeLessThanOrEqual(max);
  });
});
