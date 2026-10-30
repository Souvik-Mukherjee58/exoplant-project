import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

// Custom metrics to track latency per endpoint individually
const planetsDuration = new Trend('planets_duration', true);
const topTargetsDuration = new Trend('top_targets_duration', true);
const planetDetailDuration = new Trend('planet_detail_duration', true);
const explainDuration = new Trend('explain_duration', true);
const errorCount = new Counter('error_count');
const successRate = new Rate('successful_requests');

// Base URL configurable via environment variable: k6 run -e BASE_URL=http://localhost:8000 loadtest/api.js
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Realistic candidate planets from NASA Exoplanet Archive
const SAMPLE_PLANETS = [
  'TOI-700 d',
  'TRAPPIST-1 e',
  'K2-18 b',
  'LHS 1140 b',
  'Proxima Centauri b',
  'WASP-121 b',
  'HAT-P-26 b',
  'HD 209458 b',
  'GJ 1214 b',
  'LP 791-18 d'
];

export const options = {
  stages: [
    { duration: '10s', target: 5 },   // Warm-up ramp: 0 -> 5 VUs
    { duration: '30s', target: 20 },  // Sustained load: 20 VUs
    { duration: '10s', target: 30 },  // Peak burst: 20 -> 30 VUs
    { duration: '10s', target: 0 },   // Cool-down ramp: 30 -> 0 VUs
  ],
  thresholds: {
    // Global acceptance criteria
    'http_req_failed': ['rate<0.01'],             // Error rate must remain under 1%
    'http_req_duration': ['p(95)<150', 'p(99)<300'], // 95% of requests under 150ms, 99% under 300ms
    'successful_requests': ['rate>0.99'],          // At least 99% successful responses
    
    // Per-endpoint P95 latency thresholds
    'planets_duration': ['p(95)<100'],
    'top_targets_duration': ['p(95)<80'],
    'planet_detail_duration': ['p(95)<50'],
    'explain_duration': ['p(95)<150'],
  },
};

export default function () {
  const headers = {
    'Accept': 'application/json',
    'User-Agent': 'k6-load-tester/1.0',
  };

  // Pick a random exoplanet from our representative sample
  const planet = SAMPLE_PLANETS[Math.floor(Math.random() * SAMPLE_PLANETS.length)];
  const encodedPlanet = encodeURIComponent(planet);

  // 1. GET /api/v1/planets (Paginated listing with DuckDB query engine)
  group('Catalog Listing: /api/v1/planets', () => {
    const res = http.get(`${BASE_URL}/api/v1/planets?limit=25&offset=0&sort_by=priority`, {
      headers,
      tags: { name: 'GET /api/v1/planets' },
    });

    planetsDuration.add(res.timings.duration);
    const passed = check(res, {
      'status is 200': (r) => r.status === 200,
      'content-type is json': (r) => r.headers['Content-Type'] && r.headers['Content-Type'].includes('application/json'),
      'has etag header': (r) => !!r.headers['Etag'] || !!r.headers['ETag'],
      'returns list': (r) => {
        try {
          const body = JSON.parse(r.body);
          return Array.isArray(body) && body.length > 0;
        } catch {
          return false;
        }
      },
    });

    successRate.add(passed);
    if (!passed) errorCount.add(1);
  });

  sleep(0.1);

  // 2. GET /api/v1/top-targets (Ranked candidate list)
  group('Top Targets: /api/v1/top-targets', () => {
    const res = http.get(`${BASE_URL}/api/v1/top-targets?limit=10&exclude_observed=true`, {
      headers,
      tags: { name: 'GET /api/v1/top-targets' },
    });

    topTargetsDuration.add(res.timings.duration);
    const passed = check(res, {
      'status is 200': (r) => r.status === 200,
      'returns top targets list': (r) => {
        try {
          const body = JSON.parse(r.body);
          return Array.isArray(body) && body.length > 0;
        } catch {
          return false;
        }
      },
    });

    successRate.add(passed);
    if (!passed) errorCount.add(1);
  });

  sleep(0.1);

  // 3. GET /api/v1/planets/{name} (Point lookup in DuckDB)
  group('Planet Detail: /api/v1/planets/{name}', () => {
    const res = http.get(`${BASE_URL}/api/v1/planets/${encodedPlanet}`, {
      headers,
      tags: { name: 'GET /api/v1/planets/{name}' },
    });

    planetDetailDuration.add(res.timings.duration);
    const passed = check(res, {
      'status is 200': (r) => r.status === 200,
      'has correct planet_name': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body.planet_name === planet;
        } catch {
          return false;
        }
      },
      'has priority_score': (r) => {
        try {
          const body = JSON.parse(r.body);
          return typeof body.priority_score === 'number';
        } catch {
          return false;
        }
      },
    });

    successRate.add(passed);
    if (!passed) errorCount.add(1);
  });

  sleep(0.1);

  // 4. GET /api/v1/explain/{name} (TreeSHAP feature attribution waterfall)
  group('TreeSHAP Explain: /api/v1/explain/{name}', () => {
    const res = http.get(`${BASE_URL}/api/v1/explain/${encodedPlanet}`, {
      headers,
      tags: { name: 'GET /api/v1/explain/{name}' },
    });

    explainDuration.add(res.timings.duration);
    const passed = check(res, {
      'status is 200': (r) => r.status === 200,
      'has mathematical_invariants': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body.mathematical_invariants && typeof body.mathematical_invariants.reconstruction_error === 'number';
        } catch {
          return false;
        }
      },
      'additive conservation satisfied': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body.mathematical_invariants.reconstruction_error < 1e-6;
        } catch {
          return false;
        }
      },
    });

    successRate.add(passed);
    if (!passed) errorCount.add(1);
  });

  // Short pause before next iteration per virtual user
  sleep(0.2);
}

