import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Methodology from '../pages/Methodology';
import { methodologyApi } from '../services/api';

vi.mock('../services/api', () => ({
  methodologyApi: {
    getWeights: vi.fn(),
  },
}));

describe('Methodology Component', () => {
  const mockWeightsResponse = {
    scoring_config: {
      planetary_relevance_weight: 0.35,
      observational_accessibility_weight: 0.30,
      stellar_characteristics_weight: 0.15,
      data_quality_weight: 0.10,
      anomaly_score_weight: 0.10,
    },
    weights: {
      planetary_relevance: 0.35,
      observational_accessibility: 0.30,
      stellar_characteristics: 0.15,
      data_quality: 0.10,
      anomaly_score: 0.10,
    },
    percentages: {
      planetary_relevance: 35,
      observational_accessibility: 30,
      stellar_characteristics: 15,
      data_quality: 10,
      anomaly_score: 10,
    },
    total_weight: 1.0,
  };

  it('fetches weights from GET /api/v1/methodology/weights and renders them dynamically without hard-coded 25/25/20/15/15', async () => {
    methodologyApi.getWeights.mockResolvedValueOnce(mockWeightsResponse);

    render(<Methodology />);

    // Check that methodologyApi.getWeights was called
    expect(methodologyApi.getWeights).toHaveBeenCalled();

    await waitFor(() => {
      expect(screen.getByText('● Live Scorer Config')).toBeInTheDocument();
    });

    // Verify weights are rendered dynamically
    expect(screen.getAllByText('35%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('30%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('15%').length).toBeGreaterThan(0);

    // Verify hard-coded 25/25/20/15/15 is never present in the document
    expect(screen.queryByText(/25\/25\/20\/15\/15/)).not.toBeInTheDocument();
    expect(screen.queryByText(/25%/)).not.toBeInTheDocument();
    expect(screen.queryByText(/20%/)).not.toBeInTheDocument();
  });
});

