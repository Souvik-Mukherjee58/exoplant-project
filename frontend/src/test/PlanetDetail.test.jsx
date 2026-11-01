import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import PlanetDetail from '../pages/PlanetDetail';

// Mock 3D Visualizer and SHAP Waterfall for JSDOM
vi.mock('../components/Planet3DVisualizer', () => ({
  default: () => <div data-testid="planet-3d-visualizer">Planet 3D</div>,
}));

vi.mock('../components/ShapWaterfall', () => ({
  default: () => <div data-testid="shap-waterfall">Linear SHAP Waterfall</div>,
  ShapWaterfall: () => <div data-testid="shap-waterfall">Linear SHAP Waterfall</div>,
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

    // Asserts primary number is percentile and score tooltip with 4 decimals is present
    expect(screen.getByText(/Top 0\.1% of 4,643 eligible/i)).toBeInTheDocument();
    expect(screen.getAllByTitle('Raw score: 85.4000').length).toBeGreaterThan(0);
    expect(screen.getByText(/85\.4/)).toBeInTheDocument();

    // Asserts habitability heuristic is strictly labelled
    expect(screen.getByText('Habitability heuristic (not used for ranking)')).toBeInTheDocument();

    // Asserts default measured mass label when mass_is_estimated is false
    expect(screen.getByText('Measured Mass')).toBeInTheDocument();
  });

  it('renders "Estimated Mass (Chen & Kipping 2017)" when mass_is_estimated is true', () => {
    mockPlanetState = {
      planet: {
        planet_name: 'TRAPPIST-1 e',
        hostname: 'TRAPPIST-1',
        priority_score: 91.0,
        priority_rank: 3,
        planet_radius: 0.92,
        planet_mass: 0.77,
        mass_is_estimated: true,
        orbital_period: 6.1,
        equilibrium_temperature: 251,
        distance: 12.1,
        hz_status: 'Inside HZ',
        discovery_method: 'Transit',
      },
      loading: false,
      error: null,
    };

    render(
      <MemoryRouter initialEntries={['/planet/TRAPPIST-1%20e']}>
        <Routes>
          <Route path="/planet/:planetName" element={<PlanetDetail />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Estimated Mass (Chen & Kipping 2017)')).toBeInTheDocument();
  });

  it('renders "not in archive" with tooltip for missing physical and stellar parameters', () => {
    mockPlanetState = {
      planet: {
        planet_name: 'Mystery-Planet-b',
        hostname: 'Mystery-Star',
        priority_score: 60.0,
        priority_rank: 200,
        planet_radius: null, // missing
        planet_mass: null, // missing
        stellar_mass: null, // missing
        stellar_radius: null, // missing
        orbital_period: 10.0,
        distance: null,
        hz_status: 'Insufficient data',
        discovery_method: 'Transit',
      },
      loading: false,
      error: null,
    };

    render(
      <MemoryRouter initialEntries={['/planet/Mystery-Planet-b']}>
        <Routes>
          <Route path="/planet/:planetName" element={<PlanetDetail />} />
        </Routes>
      </MemoryRouter>
    );

    const missingElements = screen.getAllByText('not in archive');
    expect(missingElements.length).toBeGreaterThan(0);
    missingElements.forEach((el) => {
      expect(el).toHaveAttribute('title', 'Parameter not reported in NASA Exoplanet Archive');
    });
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
