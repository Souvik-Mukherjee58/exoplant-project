import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import HzBadge, { hzBadgeTone } from '../components/HzBadge';

// One badge for the habitable-zone status (audit finding F-13): nine copies had drifted apart in colour and text.
describe('HzBadge', () => {
  it('gives each status one colour', () => {
    expect(hzBadgeTone('Inside HZ')).toContain('emerald');
    expect(hzBadgeTone('Near HZ')).toContain('amber');
    for (const other of ['Outside HZ', 'Insufficient data', undefined, 'something new']) {
      expect(hzBadgeTone(other)).toContain('slate');
    }
  });

  it('shows the status, or the fallback when there is none', () => {
    const { rerender } = render(<HzBadge status="Near HZ" />);
    expect(screen.getByText('Near HZ')).toBeInTheDocument();
    rerender(<HzBadge status={null} />);
    expect(screen.getByText('Insufficient data')).toBeInTheDocument();
    rerender(<HzBadge status="" fallback="Unknown" />);
    expect(screen.getByText('Unknown')).toBeInTheDocument();
  });

  it('uses exactly one size and adds layout classes', () => {
    render(<HzBadge status="Inside HZ" size="lg" className="font-mono" />);
    const badge = screen.getByText('Inside HZ');
    expect(badge.className).toContain('text-xs');
    expect(badge.className).not.toContain('text-[10px]');
    expect(badge.className).toContain('font-mono');
  });

  it('falls back to the small size for an unknown size', () => {
    render(<HzBadge status="Inside HZ" size="huge" />);
    expect(screen.getByText('Inside HZ').className).toContain('text-[10px]');
  });
});
