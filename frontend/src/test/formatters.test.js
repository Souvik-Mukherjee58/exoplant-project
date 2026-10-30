import { describe, it, expect } from 'vitest';
import {
  formatNumber,
  formatRadius,
  formatMass,
  formatPeriod,
  formatTemperature,
  formatDistance,
  formatPercent,
  formatPriority,
  formatAnomaly,
  getHZColor,
  getHZText,
  truncate,
  capitalize,
  formatDiscoveryMethod,
  formatStellarName,
  getIneligibleTooltip,
} from '../utils/formatters';

describe('formatters', () => {
  describe('formatNumber', () => {
    it('formats numbers with given decimal places', () => {
      expect(formatNumber(3.14159, 2)).toBe('3.14');
      expect(formatNumber(3.14159, 0)).toBe('3');
    });

    it('handles null, undefined, and NaN gracefully', () => {
      expect(formatNumber(null)).toBe('—');
      expect(formatNumber(undefined)).toBe('—');
      expect(formatNumber(NaN)).toBe('—');
    });
  });

  describe('formatRadius and formatMass', () => {
    it('formats radius with Earth radius unit', () => {
      expect(formatRadius(1.23)).toBe('1.23 R⊕');
      expect(formatRadius(null)).toBe('— R⊕');
    });

    it('formats mass with Earth mass unit', () => {
      expect(formatMass(5.67)).toBe('5.67 M⊕');
    });
  });

  describe('formatDistance', () => {
    it('formats light-years', () => {
      expect(formatDistance(39.46)).toBe('39.5 ly');
      expect(formatDistance(null)).toBe('—');
    });
  });

  describe('formatPriority', () => {
    it('formats priority to 1 decimal place', () => {
      expect(formatPriority(84.37)).toBe('84.4');
      expect(formatPriority(null)).toBe('—');
    });
  });

  describe('getIneligibleTooltip', () => {
    it('formats ineligible tooltip using exclusion reason', () => {
      expect(getIneligibleTooltip({ exclusion_reason: 'Non-transiting geometry' })).toBe(
        'not eligible: Non-transiting geometry'
      );
      expect(getIneligibleTooltip({})).toBe('not eligible: non-transiting or missing parameter');
      expect(getIneligibleTooltip(null)).toBe('not eligible: non-transiting or missing parameter');
    });
  });

  describe('getHZColor and getHZText', () => {
    it('maps HZ statuses to appropriate badge classes', () => {
      expect(getHZColor('Inside HZ')).toBe('bg-emerald-500');
      expect(getHZColor('Near HZ')).toBe('bg-yellow-500');
      expect(getHZColor('Outside HZ')).toBe('bg-gray-500');
      expect(getHZColor('Insufficient data')).toBe('bg-gray-400');
      expect(getHZColor('Unknown')).toBe('bg-gray-400');
    });

    it('returns valid display text for HZ status', () => {
      expect(getHZText('Inside HZ')).toBe('Inside HZ');
      expect(getHZText('')).toBe('Insufficient data');
      expect(getHZText(null)).toBe('Insufficient data');
    });
  });
});
