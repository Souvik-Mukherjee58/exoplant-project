import React, { Suspense } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ErrorBoundary from '../components/ErrorBoundary';
import { isChunkLoadError, lazyWithRetry } from '../utils/lazyWithRetry';

// A code chunk that cannot be downloaded (network failure, or an open tab asking for a chunk that a newer
// deployment removed) once blanked the whole application: a lazy import that rejects, with no error boundary.

const CHUNK_ERROR =
  'Failed to fetch dynamically imported module: http://localhost/assets/About-x1.js';

const { reloadPage } = vi.hoisted(() => ({ reloadPage: vi.fn() }));
vi.mock('../components/ErrorBoundary', async () => {
  const actual = await vi.importActual('../components/ErrorBoundary');
  return { ...actual, reloadPage }; // jsdom cannot reload; the button must call this
});

// Two chunks that fail to load: one page and the landing page's optional chart.
vi.mock('../pages/About', () => {
  throw new TypeError(CHUNK_ERROR);
});
vi.mock('../components/ModelWeightsChart', () => {
  throw new TypeError(CHUNK_ERROR);
});

vi.mock('../components/Navbar', () => ({ default: () => <nav>site navigation</nav> }));
vi.mock('../components/Footer', () => ({ default: () => <footer>site footer</footer> }));
vi.mock('../components/Planet3DVisualizer', () => ({ default: () => <div /> }));
vi.mock('../pages/Methodology', () => ({ default: () => <h1>Methodology page</h1> }));
vi.mock('../hooks/usePlanets', () => ({
  useTopTargets: () => ({ planets: [], loading: false, error: null }),
}));
vi.mock('../hooks/useAnalytics', () => ({
  useAnalytics: () => ({ stats: null, loading: false, error: null }),
}));
vi.mock('../services/api', () => ({
  modelsApi: {
    getBenchmark: () => Promise.resolve(null),
    getFeatureImportance: () =>
      Promise.resolve({ top_features: [{ feature: 'planet_radius', coefficient: 0.8 }] }),
  },
  planetsApi: { getKnownTargets: () => Promise.resolve([]) },
}));

const { default: App, PageError } = await import('../App');
const { default: Home } = await import('../pages/Home');
const { FavoritesProvider } = await import('../context/FavoritesContext');
const { MemoryRouter } = await import('react-router-dom');

let consoleError;
beforeEach(() => {
  consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
  reloadPage.mockClear();
});
afterEach(() => {
  cleanup();
  consoleError.mockRestore();
});

const openApp = (path) => {
  window.history.pushState({}, '', path);
  return render(
    <FavoritesProvider>
      <App />
    </FavoritesProvider>
  );
};

describe('a page whose chunk fails to load', () => {
  it('shows a fallback inside the normal layout instead of a blank screen', async () => {
    openApp('/about');
    expect(
      await screen.findByRole('heading', { name: 'This page could not be loaded' })
    ).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('site navigation')).toBeInTheDocument();
    expect(screen.getByText('site footer')).toBeInTheDocument();
  });

  it('logs the failure instead of hiding it', async () => {
    openApp('/about');
    await screen.findByRole('alert');
    expect(
      consoleError.mock.calls.some((args) => String(args[0]).includes('[ExoSignal] Page /about'))
    ).toBe(true);
  });

  it('offers a reload, which fetches the current deployment', async () => {
    openApp('/about');
    fireEvent.click(await screen.findByRole('button', { name: 'Reload page' }));
    expect(reloadPage).toHaveBeenCalledTimes(1);
  });

  it('recovers when the user goes to another page', async () => {
    openApp('/about');
    fireEvent.click(await screen.findByRole('link', { name: 'Back to home' }));
    expect(
      await screen.findByRole('heading', { level: 1, name: /Target Prioritization/ })
    ).toBeInTheDocument();
    expect(screen.queryByText('This page could not be loaded')).not.toBeInTheDocument();
  });

  it('leaves the other routes working', async () => {
    openApp('/methodology');
    expect(await screen.findByRole('heading', { name: 'Methodology page' })).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});

describe('the landing page when its optional chart fails to load', () => {
  const openHome = () =>
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>
    );

  it('keeps the rest of the page and explains the missing chart', async () => {
    openHome();
    expect(
      await screen.findByText('The model-weights chart could not be loaded.')
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 1, name: /Target Prioritization/ })
    ).toBeInTheDocument();
    expect(screen.queryByText('This page could not be loaded')).not.toBeInTheDocument();
  });

  it('offers to try again and to reload; trying again keeps the page usable', async () => {
    openHome();
    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }));
    // The mocked chunk still fails: the chart fallback comes back, the page stays.
    expect(
      await screen.findByText('The model-weights chart could not be loaded.')
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Reload page' }));
    expect(reloadPage).toHaveBeenCalledTimes(1);
  });
});

describe('lazyWithRetry', () => {
  const Fallback = ({ retry }) => (
    <button type="button" onClick={retry}>
      Try again
    </button>
  );

  it('imports again after a failure, so a retry can succeed without reloading', async () => {
    const factory = vi
      .fn()
      .mockRejectedValueOnce(new TypeError(CHUNK_ERROR))
      .mockResolvedValue({ default: () => <p>chart loaded</p> });
    const Chart = lazyWithRetry(factory);
    render(
      <ErrorBoundary label="test" onRetry={Chart.retry} fallback={(p) => <Fallback {...p} />}>
        <Suspense fallback={<p>loading</p>}>
          <Chart />
        </Suspense>
      </ErrorBoundary>
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('chart loaded')).toBeInTheDocument();
    expect(factory).toHaveBeenCalledTimes(2);
  });

  it('never imports a component again once it has loaded', async () => {
    const factory = vi.fn().mockResolvedValue({ default: () => <p>loaded once</p> });
    const Page = lazyWithRetry(factory);
    const { unmount } = render(
      <Suspense fallback={null}>
        <Page />
      </Suspense>
    );
    await screen.findByText('loaded once');
    Page.retry();
    unmount();
    render(
      <Suspense fallback={null}>
        <Page />
      </Suspense>
    );
    await screen.findByText('loaded once');
    expect(factory).toHaveBeenCalledTimes(1);
  });
});

describe('the fallback text', () => {
  it('tells a download failure from another error', () => {
    const { rerender } = render(
      <MemoryRouter>
        <PageError error={new TypeError(CHUNK_ERROR)} retry={() => {}} />
      </MemoryRouter>
    );
    expect(screen.getByText(/could not be downloaded/)).toBeInTheDocument();
    rerender(
      <MemoryRouter>
        <PageError error={new Error('boom')} retry={() => {}} />
      </MemoryRouter>
    );
    expect(
      screen.getByText('An unexpected error occurred while showing this page.')
    ).toBeInTheDocument();
  });

  it.each([
    ['Failed to fetch dynamically imported module: https://x/assets/a.js', true],
    ['error loading dynamically imported module: https://x/assets/a.js', true], // Firefox
    ['Importing a module script failed.', true], // Safari
    ['Unable to preload CSS for /assets/a.css', true], // Vite
    ['Cannot read properties of undefined', false],
  ])('classifies "%s"', (message, expected) => {
    expect(isChunkLoadError(new TypeError(message))).toBe(expected);
  });
});

describe('the last-resort boundary', () => {
  it('renders a fallback when its children throw', async () => {
    const Broken = () => {
      throw new Error('render failure');
    };
    render(
      <ErrorBoundary
        label="Application"
        fallback={() => <p role="alert">ExoSignal could not be displayed</p>}
      >
        <Broken />
      </ErrorBoundary>
    );
    expect(screen.getByRole('alert')).toHaveTextContent('ExoSignal could not be displayed');
    await waitFor(() =>
      expect(
        consoleError.mock.calls.some((args) => String(args[0]).includes('[ExoSignal] Application'))
      ).toBe(true)
    );
  });
});
