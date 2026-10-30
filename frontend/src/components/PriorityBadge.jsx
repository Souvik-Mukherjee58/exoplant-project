import React from 'react';
import { formatPriority, getIneligibleTooltip } from '../utils/formatters';

export const PriorityScoreDisplay = ({ planet, className = '', showPercentile = false }) => {
  if (planet && planet.priority_score != null && !isNaN(planet.priority_score)) {
    return (
      <span className={className}>
        {formatPriority(planet.priority_score)}
        {showPercentile && planet.priority_percentile != null && (
          <span className="text-[10px] text-exosignal-text-muted ml-1">
            ({planet.priority_percentile.toFixed(0)}th %)
          </span>
        )}
      </span>
    );
  }

  const tooltip = getIneligibleTooltip(planet);
  return (
    <span
      className={`cursor-help font-mono text-slate-400 ${className}`}
      title={tooltip}
      aria-label={tooltip}
    >
      -
    </span>
  );
};

export default PriorityScoreDisplay;
