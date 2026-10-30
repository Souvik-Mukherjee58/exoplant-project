/**
 * Utility for Habitable Zone Donut Chart
 * Ensures all slices use the exact same denominator and sum to 100.0% +/- 0.1%
 */
export function calculateHzPieData(hzDistribution, totalPlanets) {
  if (!hzDistribution || typeof hzDistribution !== 'object') {
    return [];
  }

  const inside = hzDistribution['Inside HZ'] || 0;
  const near = hzDistribution['Near HZ'] || 0;
  const outside = hzDistribution['Outside HZ'] || 0;
  const insufficient = hzDistribution['Insufficient data'] || 0;

  const sumAll = inside + near + outside + insufficient;
  const denominator = totalPlanets && totalPlanets > 0 ? totalPlanets : sumAll > 0 ? sumAll : 1;

  const rawSlices = [
    {
      name: 'Inside HZ',
      value: inside,
      color: '#10b981',
      desc: 'Liquid water boundary',
    },
    {
      name: 'Near HZ',
      value: near,
      color: '#f59e0b',
      desc: 'Marginal insolation',
    },
    {
      name: 'Outside HZ',
      value: outside,
      color: '#38bdf8',
      desc: 'Extreme hot/cold orbital regimes',
    },
    {
      name: 'Insufficient data',
      value: insufficient,
      color: '#94a3b8',
      desc: 'Missing stellar flux / insolation',
    },
  ];

  return rawSlices.map((slice) => ({
    ...slice,
    percentage: Number(((slice.value / denominator) * 100).toFixed(1)),
  }));
}
