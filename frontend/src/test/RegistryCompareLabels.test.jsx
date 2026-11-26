import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import ModelRegistry from '../pages/ModelRegistry';
import Compare from '../pages/Compare';

// The committed registry entry of the active artifact, as the API returns it (without the build environment).
const artifacts = resolve(__dirname, '../../../backend/artifacts');
const version = readFileSync(resolve(artifacts, 'active_version.txt'), 'utf-8').trim();
const { environment: _hidden, ...entry } = JSON.parse(
  readFileSync(resolve(artifacts, version, 'registry_entry.json'), 'utf-8')
);

let active = null;
let versions = [];
let comparison = { metric_comparison: {} };
vi.mock('../services/api', () => ({
  registryApi: {
    getVersions: async () => ({
      active_version: versions[0]?.version,
      total_versions: versions.length,
      versions,
    }),
    getActive: async () => active,
    validate: async () => ({ valid: true, version: 'v', checks: {} }),
    compare: async () => comparison,
  },
  systemApi: {
    getLatencyBenchmark: async (iterations) => ({
      iterations,
      engine: 'DuckDB',
      p50_ms: 1.5,
      p95_ms: 2.5,
      p99_ms: 0,
    }),
  },
  explainabilityApi: {
    getComparisonExplanation: async () => ({
      planet_a: 'A b',
      planet_b: 'B b',
      score_advantage: 1,
      primary_drivers_for_advantage: [item('distance', 'Planet A', 0.3)],
      primary_drivers_for_disadvantage: [item('radius', 'Planet B', -0.2)],
      differential_waterfall: [
        item('distance', 'Planet A', 0.3),
        item('radius', 'Planet B', -0.2),
        item('mass', 'Planet B', 0),
      ],
    }),
  },
}));

function item(feature, advantage, diff) {
  return {
    feature,
    advantage,
    display_name: feature,
    planet_a_value: '1',
    planet_b_value: '2',
    diff_shap: diff,
    diff_score_impact: -diff, // points can have the other sign; they must not be shown
    abs_diff: Math.abs(diff),
  };
}

vi.mock('../hooks/usePlanets', () => {
  const planets = ['A b', 'B b'].map((planet_name) => ({ planet_name, priority_score: 50 }));
  return { usePlanets: () => ({ planets }) };
});

const row = { version, status: 'registered', registered_at: entry.registered_at };
const registry = async ({ active: a, rows = [row], metric_comparison = {} }) => {
  active = a;
  versions = rows;
  comparison = { metric_comparison };
  const view = render(<ModelRegistry />);
  await screen.findByText('Active Model Deployment');
  fireEvent.click(screen.getByRole('button', { name: /Full Governance View/ }));
  return view.container;
};

afterEach(cleanup);

describe('model registry labels', () => {
  it('makes no claim about a test set, a temporal split or a gate', async () => {
    const page = await registry({ active: { ...entry, served_model_features: 21 } });
    fireEvent.click(screen.getByRole('button', { name: /Verify SHA256 Hashes/ }));
    await screen.findByText(/file checksums compared/);
    fireEvent.click(screen.getByRole('button', { name: /Bench Latency/ }));
    await screen.findByText(/one after another/);
    fireEvent.click(screen.getByRole('button', { name: /Full Governance View/ }));
    expect(page.textContent).toContain('one after another');
    for (const shown of ['1.5 ms', '2.5 ms', '0 ms', 'Mean LatencyNot measured', 'DuckDB']) {
      expect(page.textContent).toContain(shown);
    }
    expect(page.textContent).not.toMatch(/undefined|NaN|Status:/);
    for (const claim of [
      /\(test set\)/i,
      /temporal holdout/i,
      /2017|≥ ?2022/,
      /week \d/i,
      /gating/i,
      /immutable/i,
      /atomic/i,
      /winner/i,
      /worst case/i,
      /test benchmark/i,
      /\d concurrent|concurrent multi/i,
    ]) {
      expect(page.textContent).not.toMatch(claim);
    }
    expect(page.textContent).toContain('Cross-validation grouped by host star (25 folds)');
    expect(page.textContent).toContain('No separate test set');
    expect(page.textContent).toContain('they rest on labels that are not human-verified');
    expect(page.textContent).toContain('file checksums compared');
  });

  it('shows metrics that the real entry lacks as not recorded', async () => {
    expect(entry.evaluation['ndcg@10']).toBeUndefined();
    const page = await registry({ active: { ...entry, served_model_features: 21 } });
    expect(page.textContent.match(/Not recorded/g)).toHaveLength(3);
  });

  it('shows recorded metrics, also a genuine zero, and survives null', async () => {
    const evaluation = { 'ndcg@10': 0, map: 0.4597, 'precision@10': null };
    const rows = [{ ...row, ndcg_at_10: 0, map: 0.25, precision_at_10: null }];
    const page = await registry({ active: { ...entry, evaluation }, rows });
    expect(page.textContent).toContain('0.0000');
    expect(page.textContent).toContain('0.4597');
    expect(page.textContent.match(/Not recorded/g)).toHaveLength(1);
    const cells = [...page.querySelectorAll('tbody td')].map((td) => td.textContent);
    expect(cells.slice(2, 5)).toEqual(['0.0000', '0.2500', '—']);
  });

  it('shows the number of inputs of the served model and the entry that says otherwise', async () => {
    expect(entry.training.n_features).toBe(10);
    let page = await registry({ active: { ...entry, served_model_features: 21 } });
    expect(page.textContent).toContain('Inputs of the served model:21');
    expect(page.textContent).toContain('The registry entry says 10');
    cleanup();
    page = await registry({ active: { ...entry, served_model_features: 10 } });
    expect(page.textContent).not.toContain('The registry entry says');
    cleanup();
    page = await registry({ active: { ...entry, served_model_features: null } });
    expect(page.textContent).toContain('Inputs of the served model:Not available');
  });

  it('does not invent an algorithm or a status', async () => {
    const page = await registry({
      active: { ...entry, training: {} },
      rows: [row, { ...row, version: 'v0', status: 'registered' }],
    });
    expect(page.textContent).not.toContain('Regularized Logistic Regression');
    expect(page.textContent).not.toContain('ARCHIVED');
    expect(page.textContent).toContain('REGISTERED');
  });

  it('says when there is nothing to compare and never names a winner of a tie', async () => {
    let page = await registry({ active: entry });
    fireEvent.click(screen.getByRole('button', { name: 'Compare Versions' }));
    await screen.findByText(/nothing to compare/);
    cleanup();
    const metric_comparison = { map: { [version]: 0.4, delta: 0, winner: version } };
    page = await registry({ active: entry, metric_comparison });
    fireEvent.click(screen.getByRole('button', { name: 'Compare Versions' }));
    await screen.findByText('No difference');
    expect(page.textContent).not.toContain('Higher:');
  });
});

describe('compare page labels', () => {
  const compare = async () => {
    const { container } = render(
      <MemoryRouter>
        <Compare />
      </MemoryRouter>
    );
    await waitFor(() => expect(container.textContent).toContain('Attributions of A b minus'));
    return container;
  };

  it('shows no raw LaTeX and explains what is compared', async () => {
    const text = (await compare()).textContent;
    expect(text).not.toMatch(/\\[a-zA-Z]+|\$[^$]*\$/);
    expect(text).toContain('(Δφ)');
    expect(text).toContain('This explains the model, not the planets');
    expect(text).toContain('All differences are in log-odds');
    expect(text).toContain('out-of-fold score');
    expect(text).not.toMatch(/explains precisely|ranking reversals/i);
  });

  it('never prints two signs and counts the inputs it has', async () => {
    const page = await compare();
    fireEvent.click(screen.getByRole('button', { name: 'Show all 3 inputs' }));
    expect(page.textContent).not.toMatch(/\+-|\+\+/);
    const cells = [...page.querySelectorAll('tbody tr')].map((tr) =>
      [...tr.children].slice(-2).map((td) => td.textContent)
    );
    expect(cells).toEqual([
      ['A b', '+0.30'],
      ['B b', '-0.20'],
      ['—', '0.00'],
    ]);
  });
});

describe('source text', () => {
  it.each([
    [
      'Home',
      /post-2022|Priority Score (Population|Interval)/,
      'the histogram is the heuristic; no split by year',
    ],
    ['TopTargets', /5σ/, 'the Kempton cutoff is not a detection significance'],
    ['Analytics', /empirical stellar flux/, 'the boundaries come from climate models'],
  ])('%s does not say %s (%s)', (name, pattern) => {
    const text = readFileSync(resolve(__dirname, `../pages/${name}.jsx`), 'utf-8');
    expect(text.replace(/\s+/g, ' ')).not.toMatch(pattern);
  });

  it('no page contains LaTeX, which the interface does not render', () => {
    for (const name of ['ModelRegistry', 'Compare', 'Home', 'Analytics', 'Methodology', 'About']) {
      const text = readFileSync(resolve(__dirname, `../pages/${name}.jsx`), 'utf-8');
      expect(text, name).not.toMatch(/\$\\[a-zA-Z]|\\(Delta|phi|frac|sum|odot|le|ge)\b/);
    }
  });
});
