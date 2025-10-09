/**
 * K6 Load Test Scenarios for JIT Access System (TypeScript)
 * 
 * Run with: k6 run load_test_scenarios.ts
 * 
 * Target SLO: p95 < 120ms for core endpoints
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { Options } from 'k6/options';

// Custom metrics
const errorRate = new Rate('errors');
const approvalLatency = new Trend('approval_latency');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Test data - replace with actual API keys from seed data
const REQUESTER_API_KEY = __ENV.REQUESTER_API_KEY || 'jit_test_requester';
const APPROVER_API_KEY = __ENV.APPROVER_API_KEY || 'jit_test_approver';

// Test scenarios configuration
export const options: Options = {
  scenarios: {
    // Scenario 1: Steady state request submissions
    steady_requests: {
      executor: 'constant-arrival-rate',
      rate: 10, // 10 requests per second
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 10,
      maxVUs: 50,
      exec: 'submitRequests',
    },
    
    // Scenario 2: Approval spike
    approval_spike: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 20,
      maxVUs: 100,
      stages: [
        { duration: '30s', target: 10 },
        { duration: '1m', target: 50 },
        { duration: '30s', target: 10 },
      ],
      exec: 'approveRequests',
    },
    
    // Scenario 3: Token validation load
    token_validation: {
      executor: 'constant-arrival-rate',
      rate: 100, // 100 RPS
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 50,
      maxVUs: 200,
      exec: 'validateTokens',
    },
    
    // Scenario 4: Mixed operations
    mixed_operations: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 20 },
        { duration: '2m', target: 50 },
        { duration: '1m', target: 0 },
      ],
      exec: 'mixedOperations',
    },
  },
  
  thresholds: {
    'http_req_duration': ['p(95)<120'], // 95th percentile < 120ms
    'http_req_duration{endpoint:requests}': ['p(95)<150'],
    'http_req_duration{endpoint:approve}': ['p(95)<100'],
    'http_req_duration{endpoint:tokens}': ['p(95)<200'],
    'errors': ['rate<0.05'], // Error rate < 5%
    'http_req_failed': ['rate<0.01'], // Failed request rate < 1%
  },
};

// Request payload interface
interface AccessRequestPayload {
  resource_id: number;
  duration_seconds: number;
  justification: string;
  is_break_glass: boolean;
}

interface TokenValidationPayload {
  token: string;
}

interface AccessRequest {
  id: number;
  user_id: number;
  resource_id: number;
  status: string;
}

// Scenario 1: Submit access requests
export function submitRequests(): void {
  const payload: AccessRequestPayload = {
    resource_id: 1,
    duration_seconds: 3600,
    justification: `Load test request ${__VU}-${__ITER}`,
    is_break_glass: false,
  };

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': REQUESTER_API_KEY,
    },
    tags: { endpoint: 'requests' },
  };

  const res = http.post(`${BASE_URL}/api/v1/requests`, JSON.stringify(payload), params);
  
  const success = check(res, {
    'request created': (r) => r.status === 201,
    'response time OK': (r) => r.timings.duration < 200,
  });
  
  errorRate.add(!success);
  sleep(0.1);
}

// Scenario 2: Approve requests
export function approveRequests(): void {
  // First get pending requests
  const listParams = {
    headers: {
      'X-API-Key': APPROVER_API_KEY,
    },
    tags: { endpoint: 'list-requests' },
  };

  const listRes = http.get(`${BASE_URL}/api/v1/requests?status=pending`, listParams);
  
  if (listRes.status === 200 && listRes.body) {
    const requests: AccessRequest[] = JSON.parse(listRes.body as string);
    
    if (requests.length > 0) {
      const requestId = requests[0].id;
      const startTime = Date.now();
      
      const approveParams = {
        headers: {
          'X-API-Key': APPROVER_API_KEY,
        },
        tags: { endpoint: 'approve' },
      };
      
      const approveRes = http.post(
        `${BASE_URL}/api/v1/requests/${requestId}/approve`,
        null,
        approveParams
      );
      
      const endTime = Date.now();
      const latency = endTime - startTime;
      
      const success = check(approveRes, {
        'approval successful': (r) => r.status === 200,
        'approval time OK': (r) => r.timings.duration < 150,
      });
      
      approvalLatency.add(latency);
      errorRate.add(!success);
    }
  }
  
  sleep(0.2);
}

// Scenario 3: Validate tokens
export function validateTokens(): void {
  // Use a test token (in real scenario, we'd issue tokens first)
  const payload: TokenValidationPayload = {
    token: `test_token_for_validation_${__VU}`,
  };

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
    tags: { endpoint: 'validate' },
  };

  const res = http.post(`${BASE_URL}/api/v1/tokens/validate`, JSON.stringify(payload), params);
  
  const success = check(res, {
    'validation response': (r) => r.status === 200,
    'fast validation': (r) => r.timings.duration < 50,
  });
  
  errorRate.add(!success);
  sleep(0.01);
}

// Scenario 4: Mixed operations
export function mixedOperations(): void {
  const operation = Math.random();
  
  if (operation < 0.4) {
    // 40% - List requests
    const params = {
      headers: {
        'X-API-Key': REQUESTER_API_KEY,
      },
      tags: { endpoint: 'list' },
    };
    http.get(`${BASE_URL}/api/v1/requests`, params);
    
  } else if (operation < 0.7) {
    // 30% - Submit request
    submitRequests();
    
  } else if (operation < 0.9) {
    // 20% - Check grants
    const params = {
      headers: {
        'X-API-Key': REQUESTER_API_KEY,
      },
      tags: { endpoint: 'grants' },
    };
    http.get(`${BASE_URL}/api/v1/grants/me`, params);
    
  } else {
    // 10% - Health check
    const params = {
      tags: { endpoint: 'health' },
    };
    http.get(`${BASE_URL}/health`, params);
  }
  
  sleep(0.5);
}

// Summary handler
export function handleSummary(data: any) {
  return {
    'load-test-results.json': JSON.stringify(data, null, 2),
    'stdout': textSummary(data),
  };
}

function textSummary(data: any): string {
  const httpReqs = data.metrics.http_reqs?.values?.count || 0;
  const httpFailed = data.metrics.http_req_failed?.values?.passes || 0;
  const p50 = data.metrics.http_req_duration?.values?.['p(50)']?.toFixed(2) || 0;
  const p95 = data.metrics.http_req_duration?.values?.['p(95)']?.toFixed(2) || 0;
  const p99 = data.metrics.http_req_duration?.values?.['p(99)']?.toFixed(2) || 0;
  const p95Value = parseFloat(p95);
  
  return `
  ========= Load Test Results =========
  
  Scenarios Executed: ${Object.keys(data.metrics).length}
  Total Requests: ${httpReqs}
  Failed Requests: ${httpFailed}
  
  Response Times:
    - p50: ${p50}ms
    - p95: ${p95}ms
    - p99: ${p99}ms
  
  SLO Status: ${p95Value < 120 ? 'PASS ✓' : 'FAIL ✗'}
  Target: p95 < 120ms
  
  =====================================
  `;
}

