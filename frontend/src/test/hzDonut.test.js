import { describe, it, expect } from 'vitest';
import { calculateHzPieData } from '../utils/hzDonut';

describe('calculateHzPieData', () => {
  it('includes an "Insufficient data" slice and sums to 100 +/- 0.1 with production data', () => {
    const hzDistribution = {
      'Outside HZ': 5343,
      'Insufficient data': 826,
      'Inside HZ': 182,
      'Near HZ': 100,
    };
    const totalPlanets = 6451;

    const slices = calculateHzPieData(hzDistribution, totalPlanets);

    expect(slices).toHaveLength(4);
    const names = slices.map((s) => s.name);
    expect(names).toContain('Inside HZ');
    expect(names).toContain('Near HZ');
    expect(names).toContain('Outside HZ');
    expect(names).toContain('Insufficient data');

    const insufficientSlice = slices.find((s) => s.name === 'Insufficient data');
    expect(insufficientSlice).toBeDefined();
    expect(insufficientSlice.value).toBe(826);

    // Verify all slices share the exact same denominator
    const percentageSum = slices.reduce((acc, s) => acc + s.percentage, 0);
    expect(percentageSum).toBeGreaterThanOrEqual(99.9);
    expect(percentageSum).toBeLessThanOrEqual(100.1);
  });

  it('handles missing or zero total gracefully', () => {
    const hzDistribution = {
      'Inside HZ': 25,
      'Near HZ': 25,
      'Outside HZ': 25,
      'Insufficient data': 25,
    };
    const slices = calculateHzPieData(hzDistribution, 100);
    const percentageSum = slices.reduce((acc, s) => acc + s.percentage, 0);
    expect(percentageSum).toBeCloseTo(100, 1);
  });

  it('returns empty array when distribution is null or empty', () => {
    expect(calculateHzPieData(null, 6451)).toEqual([]);
    expect(calculateHzPieData(undefined, 6451)).toEqual([]);
  });
});
