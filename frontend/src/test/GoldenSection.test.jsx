import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Home from '../pages/Home';
import { planetsApi, modelsApi } from '../services/api';

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

// Mock 3D Visualizer
vi.mock('../components/Planet3DVisualizer', () => ({
  default: () => <div data-testid="mock-planet-3d" />,
}));

// Mock hooks
const mockTopTargets = [
  {
    planet_name: 'WASP-39 b',
    hostname: 'WASP-39',
    priority_score: 99.4,
    priority_rank: 2,
    planet_radius: 14.3,
    orbital_period: 4.05,
    distance: 215.0,
    hz_status: 'Outside HZ',
    is_jwst_target: true,
    already_observed_jwst: true,
  },
  {
    planet_name: 'Unobserved-Candidate-Alpha',
    hostname: 'Candidate Star',
    priority_score: 98.2,
    priority_rank: 1,
    planet_radius: 2.1,
    orbital_period: 15.2,
    distance: 45.0,
    hz_status: 'Inside HZ',
    is_jwst_target: false,
    already_observed_jwst: false,
  },
];

vi.mock('../hooks/usePlanets', () => ({
  useTopTargets: () => ({
    planets: mockTopTargets,
    loading: false,
    error: null,
  }),
}));

vi.mock('../hooks/useAnalytics', () => ({
  useAnalytics: () => ({
    stats: {
      total_planets: 6451,
      total_transiting: 4643,
      median_priority: 45.2,
      hz_distribution: { inside_hz: 50, near_hz: 100, outside_hz: 4000 },
      priority_histogram: [],
    },
    loading: false,
    error: null,
  }),
}));

vi.mock('../services/api', () => ({
  planetsApi: {
    getKnownTargets: vi.fn(),
  },
  modelsApi: {
    getBenchmark: vi.fn(),
    getFeatureImportance: vi.fn(),
    getFeatureImportances: vi.fn(),
  },
}));

describe('Home.jsx Golden Benchmark Section', () => {
  const mockKnownTargetsResponse = [
    {
      planet_name: 'WASP-39 b',
      is_jwst_target: true,
      already_observed_jwst: true,
      oof_ml_rank: 2,
      oof_priority_score: 99.4,
      planet_radius: 14.3,
      orbital_period: 4.05,
      hz_status: 'Outside HZ',
      kempton_size_class: 'Hot Jupiter',
    },
    {
      planet_name: 'HAT-P-18 b',
      is_jwst_target: true,
      already_observed_jwst: true,
      oof_ml_rank: 5,
      oof_priority_score: 95.8,
      planet_radius: 11.2,
      orbital_period: 5.5,
      hz_status: 'Outside HZ',
      kempton_size_class: 'Saturn-like',
    },
    {
      planet_name: 'Unobserved-Planet-False-Observed',
      is_jwst_target: false,
      already_observed_jwst: false,
      priority_rank: 1,
      priority_score: 98.5,
      planet_radius: 2.3,
      orbital_period: 14.2,
      hz_status: 'Inside HZ',
    },
    {
      planet_name: 'Inconsistent-Target-Flagged-False',
      is_jwst_target: true,
      already_observed_jwst: false, // Invariant violation test case
      oof_ml_rank: 12,
      oof_priority_score: 88.0,
      planet_radius: 3.1,
      orbital_period: 21.0,
      hz_status: 'Near HZ',
    },
  ];

  it('renders ONLY verified JWST targets in the Golden Benchmark section and NEVER displays a target with already_observed_jwst == false', async () => {
    planetsApi.getKnownTargets.mockResolvedValue(mockKnownTargetsResponse);
    modelsApi.getBenchmark.mockResolvedValue({
      leaderboard: [],
      selected_production_model: {
        model_name: 'Logistic Regression (Variant A - All Features)',
        ap: 0.4597,
        ap_ci95: [0.3599, 0.5687],
        recall_at_50: 0.7459,
      },
    });
    modelsApi.getFeatureImportance.mockResolvedValue({
      top_features: [{ feature: 'transmission_snr_proxy', coefficient: 1.84 }],
    });
    modelsApi.getFeatureImportances.mockResolvedValue({
      top_features: [{ feature: 'transmission_snr_proxy', coefficient: 1.84 }],
    });

    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(
        screen.getAllByRole('heading', {
          name: /Known JWST targets: where our model ranks them/i,
        }).length
      ).toBeGreaterThan(0);
    });

    // 1. Golden Benchmark Section container
    const goldenSection = screen.getByTestId('golden-benchmark-section');
    expect(goldenSection).toBeInTheDocument();

    // 2. Verified targets WITH already_observed_jwst == true MUST appear in Golden Benchmark
    expect(within(goldenSection).getByText('WASP-39 b')).toBeInTheDocument();
    expect(within(goldenSection).getByText('OOF Rank #2')).toBeInTheDocument();
    expect(within(goldenSection).getByText('HAT-P-18 b')).toBeInTheDocument();
    expect(within(goldenSection).getByText('OOF Rank #5')).toBeInTheDocument();

    // 3. Unobserved targets (already_observed_jwst == false) MUST NEVER appear in Golden Benchmark
    expect(within(goldenSection).queryByText('Unobserved-Planet-False-Observed')).not.toBeInTheDocument();
    expect(within(goldenSection).queryByText('Inconsistent-Target-Flagged-False')).not.toBeInTheDocument();

    // 4. New recommendations section exists separately
    const recommendationsSection = screen.getByTestId('new-recommendations-section');
    expect(recommendationsSection).toBeInTheDocument();
    expect(
      within(recommendationsSection).getAllByText(/New recommendations \(not yet observed by JWST\)/i).length
    ).toBeGreaterThan(0);

    // 5. Unobserved targets appear in the New Recommendations section
    expect(within(recommendationsSection).getByText('Unobserved-Candidate-Alpha')).toBeInTheDocument();

    // 6. Confirmed targets do NOT appear in the New Recommendations section
    expect(within(recommendationsSection).queryByText('WASP-39 b')).not.toBeInTheDocument();
  });
});
