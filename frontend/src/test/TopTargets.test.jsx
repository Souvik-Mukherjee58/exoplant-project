import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import TopTargets from '../pages/TopTargets';

// Mock Recharts for JSDOM
vi.mock('recharts', async () => {
  const actual = await vi.importActual('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }) => <div data-testid="responsive-container">{children}</div>,
  };
});

// Mock FavoritesContext
vi.mock('../context/FavoritesContext', () => ({
  useFavorites: () => ({
    isFavorite: vi.fn(() => false),
    toggleFavorite: vi.fn(),
  }),
}));

const mockApiTargets = [
  {
    planet_name: 'Proxima-Centauri-b',
    hostname: 'Proxima Centauri',
    priority_score: 94.6,
    priority_rank: 1,
    planet_radius: 1.07,
    orbital_period: 11.186,
    distance: 1.3,
    hz_status: 'Inside HZ',
    anomaly_score: 0.15,
    tsm: 16.4,
    percentile_rank_string: 'Top 0.02%',
    discovery_method: 'Radial Velocity',
  },
  {
    planet_name: 'LHS-1140-b',
    hostname: 'LHS 1140',
    priority_score: 91.2,
    priority_rank: 2,
    planet_radius: 1.73,
    orbital_period: 24.737,
    distance: 15.0,
    hz_status: 'Inside HZ',
    anomaly_score: 0.22,
    tsm: 14.1,
    percentile_rank_string: 'Top 0.05%',
    discovery_method: 'Transit',
  },
  {
    planet_name: 'TRAPPIST-1-e',
    hostname: 'TRAPPIST-1',
    priority_score: 88.9,
    priority_rank: 3,
    planet_radius: 0.92,
    orbital_period: 6.099,
    distance: 12.1,
    hz_status: 'Inside HZ',
    anomaly_score: 0.31,
    tsm: 12.8,
    percentile_rank_string: 'Top 0.08%',
    discovery_method: 'Transit',
  },
];

// Mock useTopTargets hook
vi.mock('../hooks/usePlanets', () => ({
  useTopTargets: (limit) => ({
    planets: mockApiTargets.slice(0, limit),
    loading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

describe('TopTargets Component', () => {
  it('renders dynamic API targets without hard-coded numbers', () => {
    render(
      <MemoryRouter>
        <TopTargets />
      </MemoryRouter>
    );

    // Verify planet names from API data
    expect(screen.getAllByText('Proxima-Centauri-b').length).toBeGreaterThan(0);
    expect(screen.getAllByText('LHS-1140-b').length).toBeGreaterThan(0);
    expect(screen.getAllByText('TRAPPIST-1-e').length).toBeGreaterThan(0);

    // Verify dynamic TSM and percentile values from API
    expect(screen.getAllByText('Top 0.02%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Top 0.05%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('16.4').length).toBeGreaterThan(0);
    expect(screen.getAllByText('14.1').length).toBeGreaterThan(0);

    // Verify clean host star names without duplicate labels
    expect(screen.getAllByText(/Host Star:\s*Proxima Centauri/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Host Star:\s*LHS 1140/i).length).toBeGreaterThan(0);
  });

  it('renders accessible Display Top limit buttons with descriptive aria-labels', () => {
    render(
      <MemoryRouter>
        <TopTargets />
      </MemoryRouter>
    );

    // Check accessible buttons for limit presets
    const top10Btn = screen.getByRole('button', { name: /display top 10 targets/i });
    const top25Btn = screen.getByRole('button', { name: /display top 25 targets/i });
    const top50Btn = screen.getByRole('button', { name: /display top 50 targets/i });

    expect(top10Btn).toBeInTheDocument();
    expect(top25Btn).toBeInTheDocument();
    expect(top50Btn).toBeInTheDocument();
  });
});
