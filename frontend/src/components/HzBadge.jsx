import React from 'react';

/** Habitable-zone position of a planet's orbit (an orbital distance range; it says nothing about surface conditions). */
const TONES = {
  'Inside HZ': 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
  'Near HZ': 'bg-amber-500/20 text-amber-300 border-amber-500/40',
};
const OTHER_TONE = 'bg-slate-700/30 text-slate-400 border-slate-600/30';

// Tailwind resolves conflicting utilities by stylesheet order, not class order, so sizes are fixed sets.
const SIZES = {
  sm: 'px-2 py-0.5 text-[10px]',
  md: 'px-2 py-0.5 text-[11px]',
  lg: 'px-2.5 py-1 text-xs',
};

export const hzBadgeTone = (status) => TONES[status] || OTHER_TONE;

/**
 * The badge for a planet's habitable-zone status: one colour per status everywhere in the app.
 * `className` adds layout or font classes only (for example `font-mono`, `shrink-0`), never sizes or colours.
 */
const HzBadge = ({ status, fallback = 'Insufficient data', size = 'sm', className = '' }) => (
  <span
    className={`inline-block whitespace-nowrap rounded-full font-bold border ${
      SIZES[size] || SIZES.sm
    } ${hzBadgeTone(status)} ${className}`.trim()}
  >
    {status || fallback}
  </span>
);

export default HzBadge;
