---
name: load-and-performance-testing
description: Use when a stated latency or throughput requirement, or a known risk such as an aggregation endpoint or connection-pool exhaustion, needs evidence. k6 smoke, load, stress and soak scripts against the ASP.NET Core API with thresholds as pass/fail gates, run separately from the per-commit suite.
---

# Load and Performance Testing

## Quick Reference

| Topic | Rule |
|-------|------|
| Tool | k6 (JavaScript scripts, Go runtime). Alternatives only on a stated team preference |
| When | A stated latency/throughput requirement or a concrete risk. Start with one smoke script plus one load script per hot endpoint, not a suite per endpoint |
| Not a per-commit gate | Slow, needs a real target (compose stack or deployed environment). Run on a schedule, pre-release, or on demand; a small smoke can run in CI |
| Pass/fail | `options.thresholds` in the script (p95/p99 latency, error rate, checks). A breach makes k6 exit non-zero and fails the step. Thresholds come from the requirement, not invented numbers |
| Data | Realistic volume and shape, created through the API or a seed; never production data. Scaled data is its own concern |
| Secrets | Tokens and URLs via `__ENV` (`${API_BASE_URL}`, `${TEST_JWT}`), never in the script |
| Environment | Never load-test a shared environment without the owner's agreement; isolate from real users |

## Test Types

| Type | Shape | Question |
|------|-------|----------|
| Smoke | 1-5 VUs, about 1 minute | Does the happy path work under trivial load |
| Load | Ramp to expected peak, hold | Does latency stay within the requirement at expected traffic |
| Stress | Ramp past peak until failure | Where does it break, and does it degrade gracefully |
| Soak | Moderate load for hours | Leaks: connection pool, memory, handles |
| Spike | Sudden jump and drop | Recovery and autoscaling reaction |

## What to target on this stack

- List, search and aggregation endpoints; report generation and exports
- Npgsql connection pool exhaustion and slow-query amplification (a query fine at 1 rps can saturate the database at 50)
- N+1 patterns, which single-request tests cannot expose
- JWT validation overhead (remote key fetch without caching)
- Outbound dependency timeouts and retry storms

## Example: smoke with thresholds

```javascript
// perf/smoke-reports.js
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 3,
  duration: '1m',
  thresholds: {
    http_req_duration: ['p(95)<300', 'p(99)<800'],
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
  },
};

export default function () {
  const res = http.get(`${__ENV.API_BASE_URL}/api/v1/reports`, {
    headers: { Authorization: `Bearer ${__ENV.TEST_JWT}` },
  });
  check(res, { 'status is 200': (r) => r.status === 200 });
}
```

## Example: ramping load

```javascript
export const options = {
  stages: [
    { duration: '2m', target: 50 },   // ramp to expected peak
    { duration: '5m', target: 50 },   // hold
    { duration: '2m', target: 0 },
  ],
  thresholds: {
    'http_req_duration{endpoint:list}': ['p(95)<500'],
    http_req_failed: ['rate<0.02'],
  },
};

export default function () {
  const res = http.get(`${__ENV.API_BASE_URL}/api/v1/reports`, { tags: { endpoint: 'list' } });
  check(res, { ok: (r) => r.status === 200 });
  sleep(1);   // think time
}
```

Use `scenarios` with `constant-arrival-rate` when the requirement is requests per second rather than concurrent users.

## CI

```yaml
- run: docker run --rm -i -e API_BASE_URL -e TEST_JWT grafana/k6 run - < perf/smoke-reports.js
  env:
    API_BASE_URL: ${{ vars.PERF_API_URL }}
    TEST_JWT: ${{ secrets.PERF_TEST_JWT }}
```

Pin the k6 image tag (verify the current one). Export results to your metrics backend (`--out`) to compare runs; alert on regression versus the last baseline.

## Reading results

Check the generator is not the bottleneck (k6 CPU), then correlate with server metrics: CPU, pool usage, database wait events, GC. A latency curve that bends upward before CPU saturates points at a lock, pool or downstream limit. Record findings and the tuning decision; rerun to confirm.

## Quality Checklist

- [ ] Requirement stated; thresholds derive from it
- [ ] Thresholds in the script; non-zero exit fails the pipeline
- [ ] Realistic, non-production data and think time
- [ ] Secrets and URLs from environment
- [ ] Target isolated and owner agreed
- [ ] Results compared with a baseline and recorded

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| "It did not crash" as a pass | Declared thresholds |
| Load test in the per-commit suite | Separate scheduled or pre-release job |
| Hammering one cached id | Varied realistic requests |
| Tuning without a baseline | Measure, change one thing, remeasure |

## Related Skills

- `writing-integration-tests`: correctness before scale
- `writing-playwright-e2e-tests`: functional journeys
