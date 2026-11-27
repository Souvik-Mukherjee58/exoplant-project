import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CanceledError } from 'axios';
import { planetsApi } from '../services/api';
import { usePlanetDetail, usePlanets } from '../hooks/usePlanets';
import { FavoritesProvider } from '../context/FavoritesContext';
import Explorer from '../pages/Explorer';

vi.mock('../services/api', () => ({
  planetsApi: { getAll: vi.fn(), getByName: vi.fn(), getTopTargets: vi.fn() },
  explainabilityApi: { getPlanetExplanation: vi.fn(() => new Promise(() => {})) },
}));

/** A promise the test settles by hand, so responses can arrive in any chosen order. */
function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/** Each call returns the next deferred promise and records the signal it received. */
function queueResponses(mockFn, count) {
  const calls = Array.from({ length: count }, () => deferred());
  const signals = [];
  let i = 0;
  mockFn.mockImplementation((...args) => {
    signals.push(args[args.length - 1]?.signal);
    return calls[i++].promise;
  });
  return { calls, signals };
}

const PlanetsProbe = ({ params }) => {
  const { planets, loading, error } = usePlanets(params);
  return (
    <div>
      <span data-testid="names">{planets.map((p) => p.planet_name).join(',')}</span>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="error">{error ?? ''}</span>
    </div>
  );
};

const DetailProbe = ({ name }) => {
  const { planet, loading, error } = usePlanetDetail(name);
  return (
    <div>
      <span data-testid="planet">{planet?.planet_name ?? ''}</span>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="error">{error ?? ''}</span>
    </div>
  );
};

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.useRealTimers());

describe('usePlanets: an older response never overwrites a newer one', () => {
  it('keeps the newer result when the older request resolves last', async () => {
    const { calls, signals } = queueResponses(planetsApi.getAll, 2);
    const { rerender } = render(<PlanetsProbe params={{ q: 'kep' }} />);
    rerender(<PlanetsProbe params={{ q: 'kepler' }} />);

    expect(signals[0].aborted).toBe(true); // request A was cancelled when B started
    expect(signals[1].aborted).toBe(false);

    await act(async () => calls[1].resolve([{ planet_name: 'Kepler-452 b' }])); // B first
    await act(async () => calls[0].resolve([{ planet_name: 'Kepler-10 b' }])); // A afterwards

    expect(screen.getByTestId('names').textContent).toBe('Kepler-452 b');
    expect(screen.getByTestId('loading').textContent).toBe('false');
    expect(screen.getByTestId('error').textContent).toBe('');
  });

  it('does not report a cancelled request as an error', async () => {
    const { calls } = queueResponses(planetsApi.getAll, 2);
    const { rerender } = render(<PlanetsProbe params={{ q: 'a' }} />);
    rerender(<PlanetsProbe params={{ q: 'ab' }} />);
    await act(async () => calls[0].reject(new CanceledError('canceled')));
    await act(async () => calls[1].resolve([{ planet_name: 'AB Pic b' }]));
    expect(screen.getByTestId('error').textContent).toBe('');
    expect(screen.getByTestId('names').textContent).toBe('AB Pic b');
  });

  it('still reports a real failure of the current request', async () => {
    const { calls } = queueResponses(planetsApi.getAll, 1);
    render(<PlanetsProbe params={{ q: 'x' }} />);
    await act(async () => calls[0].reject(new Error('503')));
    expect(screen.getByTestId('error').textContent).toBe('Failed to load exoplanet data');
    expect(screen.getByTestId('loading').textContent).toBe('false');
  });

  it('cancels the request on unmount and ignores its late response', async () => {
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { calls, signals } = queueResponses(planetsApi.getAll, 1);
    const { unmount } = render(<PlanetsProbe params={{ q: 'x' }} />);
    unmount();
    expect(signals[0].aborted).toBe(true);
    await act(async () => calls[0].resolve([{ planet_name: 'late' }]));
    expect(errors).not.toHaveBeenCalled();
    errors.mockRestore();
  });
});

describe('usePlanetDetail: quick navigation between planets', () => {
  it('shows the planet navigated to last, whatever the response order', async () => {
    const { calls } = queueResponses(planetsApi.getByName, 3);
    const { rerender } = render(<DetailProbe name="TOI-700 d" />);
    rerender(<DetailProbe name="TRAPPIST-1 e" />);
    rerender(<DetailProbe name="LHS 1140 b" />);

    await act(async () => calls[2].resolve({ planet_name: 'LHS 1140 b' }));
    await act(async () => calls[0].resolve({ planet_name: 'TOI-700 d' }));
    await act(async () => calls[1].resolve({ planet_name: 'TRAPPIST-1 e' }));

    expect(screen.getByTestId('planet').textContent).toBe('LHS 1140 b');
    expect(screen.getByTestId('loading').textContent).toBe('false');
  });

  it('sends no request without a planet name and is not left loading', () => {
    render(<DetailProbe name="" />);
    expect(planetsApi.getByName).not.toHaveBeenCalled();
    expect(screen.getByTestId('loading').textContent).toBe('false');
  });
});

describe('Explorer search', () => {
  it('sends one request after typing settles, not one per keystroke', async () => {
    vi.useFakeTimers();
    planetsApi.getAll.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <FavoritesProvider>
          <Explorer />
        </FavoritesProvider>
      </MemoryRouter>
    );
    await act(async () => {});
    const initialCalls = planetsApi.getAll.mock.calls.length; // the first page load
    const input = screen.getByPlaceholderText(/e\.g\. kepler 452 b, TOI-700/i);

    for (const text of ['k', 'ke', 'kep', 'kepl', 'keple', 'kepler']) {
      fireEvent.change(input, { target: { name: 'name', value: text } });
      await act(async () => vi.advanceTimersByTime(100)); // faster than the 250 ms debounce
    }
    expect(planetsApi.getAll.mock.calls.length).toBe(initialCalls);

    await act(async () => vi.advanceTimersByTime(250));
    const later = planetsApi.getAll.mock.calls.slice(initialCalls);
    expect(later).toHaveLength(1);
    expect(later[0][0]).toMatchObject({ q: 'kepler' });
  });
});
