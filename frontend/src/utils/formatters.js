/**
 * Format a number with specified decimal places
 */
export function formatNumber(value, decimals = 2) {
  if (value === null || value === undefined || isNaN(value)) {
    return '—';
  }
  return value.toFixed(decimals);
}

/**
 * Format planet radius in Earth radii
 */
export function formatRadius(value) {
  return formatNumber(value, 2) + ' R⊕';
}

/**
 * Format planet mass in Earth masses
 */
export function formatMass(value) {
  return formatNumber(value, 2) + ' M⊕';
}

/**
 * Format orbital period in days
 */
export function formatPeriod(value) {
  return formatNumber(value, 1) + ' days';
}

/**
 * Format temperature in Kelvin
 */
export function formatTemperature(value) {
  return formatNumber(value, 0) + ' K';
}

/**
 * Format distance (raw data is in light-years)
 */
export function formatDistance(value) {
  if (value === null || value === undefined || isNaN(value)) {
    return '—';
  }
  return value.toFixed(1) + ' ly';
}

/**
 * Format percentage
 */
export function formatPercent(value, decimals = 1) {
  if (value === null || value === undefined || isNaN(value)) {
    return '—';
  }
  return value.toFixed(decimals) + '%';
}

/**
 * Format priority score
 */
export function formatPriority(value) {
  return formatNumber(value, 1);
}

/**
 * Format ineligible tooltip for non-ranked planets
 */
export function getIneligibleTooltip(planet) {
  const reason = planet?.exclusion_reason || 'non-transiting or missing parameter';
  return `not eligible: ${reason}`;
}

/**
 * Format anomaly score
 */
export function formatAnomaly(value) {
  return formatNumber(value, 2);
}

/**
 * Get HZ status color class
 */
export function getHZColor(status) {
  const colors = {
    'Inside HZ': 'bg-emerald-500',
    'Near HZ': 'bg-yellow-500',
    'Outside HZ': 'bg-gray-500',
    'Insufficient data': 'bg-gray-400',
  };
  return colors[status] || colors['Insufficient data'];
}

/**
 * Get HZ status display text
 */
export function getHZText(status) {
  return status || 'Insufficient data';
}

/**
 * Truncate text to specified length
 */
export function truncate(text, maxLength = 50) {
  if (!text || text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '…';
}

/**
 * Capitalize first letter
 */
export function capitalize(text) {
  if (!text) return '';
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * Format discovery method
 */
export function formatDiscoveryMethod(method) {
  if (!method) return '—';
  return method;
}

/**
 * Format stellar name without duplicate "Host Star" bugs
 */
export function getCleanHostStar(planet) {
  if (!planet) return '—';
  const raw = planet.hostname || planet.stellar_name;
  if (raw && raw.trim().toLowerCase() !== 'host star') {
    return raw.trim();
  }
  if (planet.planet_name) {
    const derived = planet.planet_name.replace(/\s+[a-z]$/i, '').trim();
    if (derived && derived.toLowerCase() !== 'host star') {
      return derived;
    }
  }
  return '—';
}

export function formatStellarName(name) {
  if (!name || name.trim().toLowerCase() === 'host star') return 'Unknown';
  return name;
}
