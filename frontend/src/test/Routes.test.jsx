import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { FavoritesProvider } from '../context/FavoritesContext';

// Routing contract of the application; it must hold across router upgrades.

vi.mock('../components/Navbar', () => ({ default: () => <div /> }));
vi.mock('../components/Footer', () => ({ default: () => <div /> }));
const { page } = vi.hoisted(() => ({ page: (name) => ({ default: () => name }) }));
vi.mock('../pages/Home', () => page('home'));
vi.mock('../pages/Explorer', () => page('explorer'));
vi.mock('../pages/TopTargets', () => page('top-targets'));
vi.mock('../pages/Favorites', () => page('favorites'));
vi.mock('../pages/Analytics', () => page('analytics'));
vi.mock('../pages/ModelRegistry', () => page('registry'));
vi.mock('../pages/Methodology', () => page('methodology'));
vi.mock('../pages/About', () => page('about'));
vi.mock('../pages/Compare', async () => {
  const { useSearchParams } = await import('react-router-dom');
  return {
    default: function Compare() {
      const [params] = useSearchParams();
      return <p>{`compare ${params.get('planet_a')}`}</p>;
    },
  };
});
vi.mock('../pages/PlanetDetail', async () => {
  const { useParams } = await import('react-router-dom');
  return {
    default: function PlanetDetail() {
      return <p>{`planet ${useParams().planetName}`}</p>;
    },
  };
});

const open = (path) => {
  window.history.pushState({}, '', path);
  render(
    <FavoritesProvider>
      <App />
    </FavoritesProvider>
  );
};

afterEach(cleanup);

describe('routes', () => {
  it.each([
    ['/', 'home'],
    ['/explorer', 'explorer'],
    ['/top-targets', 'top-targets'],
    ['/favorites', 'favorites'],
    ['/analytics', 'analytics'],
    ['/registry', 'registry'],
    ['/methodology', 'methodology'],
    ['/about', 'about'],
  ])('%s shows %s', (path, text) => {
    open(path);
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it.each(['WASP-39 b', 'TRAPPIST-1 e', '2MASS J0249-0557 c', 'BD+20 594 b', 'a/b%c'])(
    'decodes the planet name %s',
    (name) => {
      open(`/planet/${encodeURIComponent(name)}`);
      expect(screen.getByText(`planet ${name}`)).toBeInTheDocument();
    }
  );

  it('reads the comparison query', () => {
    open(`/compare?planet_a=${encodeURIComponent('BD+20 594 b')}`);
    expect(screen.getByText('compare BD+20 594 b')).toBeInTheDocument();
  });

  it('shows a message for an unknown nested address', () => {
    open('/no/such/page');
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });
});
