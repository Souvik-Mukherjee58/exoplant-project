import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import PlanetDetail from '../pages/PlanetDetail';

// Mock 3D Visualizer and SHAP Waterfall for JSDOM
vi.mock('../components/Planet3DVisualizer', () => ({
  default: () => <div data-testid="planet-3d-visualizer">Planet 3D</div>,
}));

vi.mock('../components/TreeSHAPWaterfall', () => ({
  default: () => <div data-testid="treeshap-waterfall">TreeSHAP Waterfall</div>,
}));

let mockPlanetState = {
  planet: null,
  loading: false,
  error: null,
};

vi.mock('../hooks/usePlanets', () => ({
  usePlanetDetail: () => mockPlanetState,
}));

describe('PlanetDetail Component', () => {
  it('shows the correct planet and its physical parameters', () => {
    mockPlanetState = {
      planet: {
        planet_name: 'Kepler-452 b',
        hostname: 'Kepler-452',
        priority_score: 85.4,
        priority_rank: 5,
        planet_radius: 1.63,
        planet_mass: 5.0,
        orbital_period: 384.8,
        equilibrium_temperature: 265,
        distance: 550.0,
        hz_status: 'Inside HZ',
        anomaly_score: 0.18,
        discovery_method: 'Transit',
        target_priority_score: 82.0,
      },
      loading: false,
      error: null,
    };

    render(
      <MemoryRouter initialEntries={['/planet/Kepler-452%20b']}>
        <Routes>
          <Route path="/planet/:planetName" element={<PlanetDetail />} />
        </Routes>
      </MemoryRouter>
    );

    // Asserts correct planet is shown
    expect(screen.getByRole('heading', { level: 1, name: 'Kepler-452 b' })).toBeInTheDocument();

    // Asserts clean host star (not "Host Star: Host Star")
    expect(screen.getByText(/Host Star:\s*Kepler-452/i)).toBeInTheDocument();

    // Asserts valid priority score
    expect(screen.getByText('85.4')).toBeInTheDocument();

    // Asserts habitability heuristic is strictly labelled
    expect(screen.getByText('Habitability heuristic (not used for ranking)')).toBeInTheDocument();
  });

  it('renders "-" with tooltip for an ineligible target', () => {
    mockPlanetState = {
      planet: {
        planet_name: 'Barnard-b',
        hostname: 'Barnard Star',
        priority_score: null,
        exclusion_reason: 'Non-transiting',
        planet_radius: 1.35,
        planet_mass: 3.2,
        orbital_period: 233.0,
        equilibrium_temperature: 105,
        distance: 1.8,
        hz_status: 'Outside HZ',
        anomaly_score: 0.42,
        discovery_method: 'Radial Velocity',
        target_priority_score: 45.0,
      },
      loading: false,
      error: null,
    };

    render(
      <MemoryRouter initialEntries={['/planet/Barnard-b']}>
        <Routes>
          <Route path="/planet/:planetName" element={<PlanetDetail />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { level: 1, name: 'Barnard-b' })).toBeInTheDocument();

    // Ineligible target should show "-" with tooltip "not eligible: Non-transiting"
    const ineligibleDash = screen.getByTitle('not eligible: Non-transiting');
    expect(ineligibleDash).toBeInTheDocument();
    expect(ineligibleDash).toHaveTextContent('-');

    // Habitability heuristic must be labelled strictly as not used for ranking
    expect(screen.getByText('Habitability heuristic (not used for ranking)')).toBeInTheDocument();
  });
});
