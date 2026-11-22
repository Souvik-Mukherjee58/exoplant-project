// Open-model capacity probe: a fixed arrival rate (requests/second) regardless of response time.
// Run once per rate by scripts/run_capacity_curve.py; the curve of p95 vs rate shows where the server
// saturates. Closed-model VU tests (loadtest/api.js) under-report saturation because slow responses
// throttle the offered load.
//
//   k6 run -e BASE_URL=http://localhost:8000 -e RATE=100 -e DURATION=60s loadtest/capacity.js

import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const RATE = parseInt(__ENV.RATE || '50', 10);
const DURATION = __ENV.DURATION || '60s';

// Read-only endpoints in a fixed mix (detail pages dominate real traffic on a catalog site).
const PLANETS = ['TRAPPIST-1 e', 'K2-18 b', 'WASP-39 b', 'LHS 1140 b', 'TOI-270 d', 'GJ 1214 b'];
const PATHS = [
  () =>
    `/api/v1/planets/${encodeURIComponent(PLANETS[Math.floor(Math.random() * PLANETS.length)])}`,
  () =>
    `/api/v1/planets/${encodeURIComponent(PLANETS[Math.floor(Math.random() * PLANETS.length)])}`,
  () => '/api/v1/top-targets?limit=25',
  () => '/api/v1/planets?limit=50',
  () =>
    `/api/v1/planets/${encodeURIComponent(
      PLANETS[Math.floor(Math.random() * PLANETS.length)]
    )}/explain`,
];

export const options = {
  scenarios: {
    fixed_rate: {
      executor: 'constant-arrival-rate',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: Math.max(10, RATE),
      maxVUs: Math.max(50, RATE * 4),
    },
  },
  summaryTrendStats: ['avg', 'med', 'p(95)', 'p(99)', 'max'],
};

export default function () {
  const path = PATHS[Math.floor(Math.random() * PATHS.length)]();
  const res = http.get(`${BASE_URL}${path}`, { headers: { Accept: 'application/json' } });
  check(res, { 'status is 200': (r) => r.status === 200 });
}
