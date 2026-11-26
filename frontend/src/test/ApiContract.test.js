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

  it('formats with the same Prettier version as the commit hook', () => {
    const hooks = readFileSync(resolve(root, '.pre-commit-config.yaml'), 'utf-8');
    const rev = hooks.match(/mirrors-prettier\s+rev: v([\d.]+)/)[1];
    const dependencies = JSON.parse(
      readFileSync(resolve(root, 'frontend/package.json'), 'utf-8')
    ).devDependencies;
    expect(dependencies.prettier).toBe(rev);
  });

  it('checks the formatting in CI, and no CI step hides a failure', () => {
    const ci = readFileSync(resolve(root, '.github/workflows/ci.yml'), 'utf-8');
    const job = ci.slice(ci.indexOf('  frontend-build:'), ci.indexOf('  docker-build:'));
    expect(job).toMatch(/- name: Check formatting[^\n]*\n\s+run: npm run format:check\n/);
    expect(job.indexOf('npm ci')).toBeLessThan(job.indexOf('format:check'));
    expect(ci).toContain('run: python ../scripts/reproduce_artifact.py');
    const workflows = resolve(root, '.github/workflows');
    for (const name of readdirSync(workflows)) {
      const text = readFileSync(resolve(workflows, name), 'utf-8');
      expect(text, name).not.toMatch(/continue-on-error: true|\|\| true/);
    }
    for (const [block] of ci.matchAll(/run: \|\n(?: {10,}[^\n]*\n)+/g)) {
      if (block.includes('| tee')) expect(block).toContain('set -o pipefail');
    }
    const { scripts } = JSON.parse(readFileSync(resolve(root, 'frontend/package.json'), 'utf-8'));
    expect(scripts['format:check']).toBe('prettier --check "src/**/*.{js,jsx,css}"');
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
