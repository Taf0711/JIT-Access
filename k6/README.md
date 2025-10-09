# K6 Load Tests

Load testing scenarios for the JIT Access system using k6.

## Prerequisites

Install k6: https://k6.io/docs/getting-started/installation/

## Running Tests

```bash
# Run with default settings
k6 run load_test_scenarios.ts

# Run with custom base URL
k6 run -e BASE_URL=http://localhost:8000 load_test_scenarios.ts

# Run with API keys from seed data
k6 run \
  -e BASE_URL=http://localhost:8000 \
  -e REQUESTER_API_KEY=your_requester_key \
  -e APPROVER_API_KEY=your_approver_key \
  load_test_scenarios.ts

# Run specific scenario only
k6 run --scenario steady_requests load_test_scenarios.ts
```

## Test Scenarios

1. **Steady Requests** (10 RPS): Continuous access request submissions
2. **Approval Spike** (5-50 RPS): Ramping approval load
3. **Token Validation** (100 RPS): High-frequency token checks
4. **Mixed Operations**: Realistic mix of all operations

## Performance Targets

- **p95 Latency**: < 120ms for all endpoints
- **Error Rate**: < 5%
- **Failed Requests**: < 1%

## Results

Results are saved to `load-test-results.json` after each run.

