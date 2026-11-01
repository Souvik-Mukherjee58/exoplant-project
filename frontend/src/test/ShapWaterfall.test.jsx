import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ShapWaterfall from '../components/ShapWaterfall';
import { explainabilityApi } from '../services/api';

vi.mock('../services/api', () => ({
  explainabilityApi: {
    getPlanetExplanation: vi.fn(),
  },
}));

describe('ShapWaterfall Component (Linear SHAP)', () => {
  const mockKepler452bExplanation = {
    planet_name: 'Kepler-452 b',
    priority_score: 85.4,
    citation: 'Lundberg & Lee (2017, NeurIPS)',
    base_logit: -1.234,
    final_logit: 1.766,
    converted_percentile: 85.4,
    mathematical_invariants: {
      base_margin: -1.234,
      sum_shap_margin: 3.0,
      predicted_margin: 1.766,
      reconstruction_error: 0.0,
    },
    top_positive_drivers: [
      {
        feature: 'transit_depth',
        shap_value: 1.5,
        feature_value: 1200.0,
        abs_importance: 1.5,
      },
      {
        feature: 'transmission_snr_proxy',
        shap_value: 0.014,
        feature_value: 2.5,
        abs_importance: 0.014,
      },
    ],
    top_negative_barriers: [
      {
        feature: 'k_magnitude',
        shap_value: -0.021,
        feature_value: 14.5,
        abs_importance: 0.021,
      },
    ],
    full_waterfall: [
      {
        feature: 'transit_depth',
        shap_value: 1.5,
        feature_value: 1200.0,
        abs_importance: 1.5,
      },
      {
        feature: 'transmission_snr_proxy',
        shap_value: 0.014,
        feature_value: 2.5,
        abs_importance: 0.014,
      },
      {
        feature: 'k_magnitude',
        shap_value: -0.021,
        feature_value: 14.5,
        abs_importance: 0.021,
      },
    ],
  };

  it('renders Linear SHAP explanation for Kepler-452 b with log-odds units and Lundberg & Lee citation', async () => {
    explainabilityApi.getPlanetExplanation.mockResolvedValueOnce(mockKepler452bExplanation);

    render(
      <ShapWaterfall planetName="Kepler-452 b" mlRank={5} rankDelta={2} />
    );

    // Initial loading indicator
    expect(screen.getByText(/Computing exact Linear SHAP feature attributions/i)).toBeInTheDocument();

    // Await async fetch resolution
    await waitFor(() => {
      expect(screen.getByText('Linear SHAP Interpretability Waterfall')).toBeInTheDocument();
    });

    // 1. Citation (Lundberg & Lee 2017, NeurIPS)
    expect(screen.getByText('Lundberg & Lee (2017, NeurIPS)')).toBeInTheDocument();

    // 2. Units: Δ log-odds
    const deltaLogOddsLabels = screen.getAllByText(/Δ log-odds/i);
    expect(deltaLogOddsLabels.length).toBeGreaterThan(0);

    // 3. Base Value (w₀)
    expect(screen.getByText('-1.234')).toBeInTheDocument();
    expect(screen.getByText('Base Value (w₀)')).toBeInTheDocument();

    // 4. Final Logit
    expect(screen.getByText('+1.766')).toBeInTheDocument();
    expect(screen.getByText('Final Logit (w·x + w₀)')).toBeInTheDocument();

    // 5. Converted Percentile
    expect(screen.getByText(/85\.4/)).toBeInTheDocument();
    expect(screen.getByText(/Converted Percentile/i)).toBeInTheDocument();

    // 6. No contribution displays as 0.0 when |phi| > 0.01
    // The value 0.014 must render as +0.014 Δ log-odds, never 0.0 or 0.00
    expect(screen.getByText('+0.014 Δ log-odds')).toBeInTheDocument();
    expect(screen.getByText('-0.021 Δ log-odds')).toBeInTheDocument();
    expect(screen.queryByText('0.0 Δ log-odds')).not.toBeInTheDocument();
    expect(screen.queryByText('0.00 Δ log-odds')).not.toBeInTheDocument();
  });
});
