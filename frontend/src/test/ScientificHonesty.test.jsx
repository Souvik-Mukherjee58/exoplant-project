import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import PlanetDetail from '../pages/PlanetDetail';
import { archiveValues, PLANET_PRESETS } from '../components/Planet3DVisualizer';

vi.mock('../components/ShapWaterfall', () => ({
  default: () => <div data-testid="waterfall" />,
  ShapWaterfall: () => <div data-testid="waterfall" />,
}));

vi.mock('../components/Planet3DVisualizer', async (importActual) => ({
  ...(await importActual()),
  default: () => <div />,
}));

let planet = null;
vi.mock('../hooks/usePlanets', () => ({
  usePlanetDetail: () => ({ planet, loading: false, error: null }),
}));

// Regression tests for the interface defects found in the 2026-11-24 repository review.

const show = (data) => {
  planet = { planet_name: 'Test b', priority_components: {}, ...data };
  return render(
    <MemoryRouter initialEntries={['/planet/Test%20b']}>
      <Routes>
        <Route path="/planet/:planetName" element={<PlanetDetail />} />
      </Routes>
    </MemoryRouter>
  ).container.textContent;
};

describe('missing values are never replaced by plausible ones', () => {
  it('does not claim a position, temperature or discovery method it does not know', () => {
    const text = show({ hz_status: 'Insufficient data', priority_score: 50, priority_rank: 3 });
    expect(text).toContain('habitable zone position is unknown');
    expect(text).toContain('no equilibrium temperature in the archive');
    expect(text).toContain('Discovery: not in archive');
    expect(text).not.toContain('~0 K');
    expect(text).not.toContain('outside the model habitable zone');
  });

  it('shows no rank shift when there is none', () => {
    expect(show({ priority_score: 50, priority_rank: 3, rank_delta: null })).not.toContain('null');
  });

  it('shows the stellar temperature the API sends', () => {
    expect(show({ stellar_effective_temperature: 2566 })).toContain('2566 K');
  });

  it('does not ask for an attribution of a planet that the model does not rank', () => {
    show({ eligible_for_transmission: false, exclusion_reason: 'Non-transiting' });
    fireEvent.click(screen.getByRole('button', { name: /Full Target Dossier/ }));
    expect(document.body.textContent).toContain('the model does not rank this planet');
    expect(screen.queryByTestId('waterfall')).toBeNull();
    cleanup();
    show({ eligible_for_transmission: true });
    fireEvent.click(screen.getByRole('button', { name: /Full Target Dossier/ }));
    expect(screen.getByTestId('waterfall')).toBeTruthy();
    cleanup();
  });

  it('shows distances in parsecs and light-years', () => {
    expect(show({ distance: 12.43 })).toContain('12.4 pc (40.5 ly)');
  });

  it('suggests transmission spectroscopy only when the archive says that the planet transits', () => {
    const methods = (data) => {
      show({ discovery_method: 'Transit', ...data });
      fireEvent.click(screen.getByRole('button', { name: /Full Target Dossier/ }));
      const text = document.body.textContent;
      cleanup();
      return text;
    };
    expect(methods({ is_transiting: false })).not.toContain('Transmission Spectroscopy (JWST');
    expect(methods({ is_transiting: true })).toContain('Transmission Spectroscopy (JWST');
  });
});

describe('planet illustration', () => {
  it('stores no physical values', () => {
    for (const preset of Object.values(PLANET_PRESETS)) {
      for (const key of ['radius', 'teq', 'period', 'transitDepth']) {
        expect(preset).not.toHaveProperty(key);
      }
    }
  });

  it('computes values from the API planet only', () => {
    expect(archiveValues(null)).toEqual({ radius: '—', teq: '—', period: '—', transitDepth: '—' });
    expect(
      archiveValues({
        planet_radius: 2.37,
        equilibrium_temperature: 284,
        orbital_period: 32.94,
        stellar_radius: 0.411,
      })
    ).toEqual({ radius: '2.37 R⊕', teq: '284 K', period: '32.9 days', transitDepth: '0.28%' });
  });
});

it('never writes a planet name in capitals: a capital letter means a stellar companion', () => {
  show({ planet_name: 'TRAPPIST-1 e' });
  expect(screen.getByRole('heading', { level: 1 }).className).toContain('normal-case');
  cleanup();
});

describe('source text', () => {
  const files = (dir) =>
    readdirSync(dir).flatMap((name) => {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) return name === 'test' ? [] : files(path);
      return /\.jsx?$/.test(name) ? [path] : [];
    });
  const root = resolve(__dirname, '..');
  const source = files(root).map((path) => [path, readFileSync(path, 'utf-8')]);

  it.each([
    [/confirmed JWST/i, 'labels are not human-verified'],
    [/verified JWST/i, 'labels are not human-verified'],
    [/liquid-water habitable/i, 'the habitable zone does not show that a planet has water'],
    [/exhibits? highest|high-yield/i, 'unsupported comparison'],
    [/(trappist|toi700|wasp96): \d/, 'invented values for a real planet'],
    [/\?\? 0\.\d{2,}/, 'hard-coded metric as fallback'],
    [/production-grade|state-of-the-art/i, 'unsupported quality claim'],
    [/percentile_rank \|\| \d/, 'invented percentile'],
    [/_score \?\? 0\b/, 'a missing score shown as 0'],
    [
      /zero (host-star )?leakage|prime target|high yield|discovery yield/i,
      'promotional or unsupported',
    ],
    [
      /high-performance|ultra-fast|authoritative|empirically grounded/i,
      'unsupported quality claim',
    ],
    [/ground truth/i, 'the labels are not ground truth'],
    [
      /already[- ]observed JWST|unobserved (targets|candidate)/i,
      'the labels do not show what JWST has observed',
    ],
    [/(logit|margin|percentage|coefficient|gain) (\?\?|\|\|) 0\b/, 'a missing number shown as 0'],
  ])('%s does not appear (%s)', (pattern) => {
    expect(source.filter(([, text]) => pattern.test(text)).map(([path]) => path)).toEqual([]);
  });
});
