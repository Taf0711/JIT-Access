# JIT Access Demo Script

This guide walks through a complete demonstration of the JIT Access system.

## Prerequisites

- Docker and Docker Compose installed
- Terminal/command line access
- Web browser (for Swagger UI and Grafana)

## Setup (5 minutes)

### 1. Start the System

```bash
# Clone and navigate to the project
cd /path/to/JIT_access

# Start all services
docker compose up -d

# Wait for services to be healthy (30 seconds)
docker compose ps
```

You should see all services running:
- `jit-app` - FastAPI application
- `jit-postgres` - PostgreSQL database
- `jit-redis` - Redis cache
- `jit-opa` - OPA policy engine
- `jit-prometheus` - Metrics collection
- `jit-grafana` - Dashboards

### 2. Seed Sample Data

```bash
# Seed the database
docker compose exec app python scripts/seed.py
```

This creates:
- **5 users**: 1 admin, 2 approvers, 2 requesters
- **10 resources**: databases, APIs, services
- **5 policies**: with different TTL rules
- **5 sample requests**: for demonstration

**Save the API keys displayed** - you'll need them!

Example output:
```
admin@example.com (admin): jit_xxxxx
approver1@example.com (approver): jit_yyyyy
requester1@example.com (requester): jit_zzzzz
```

## Demo Flow

### Part 1: Standard Access Request (10 minutes)

#### Step 1: View Available Resources

```bash
# Set your requester API key
export REQUESTER_KEY="jit_your_requester_key_here"

# List available resources
curl -H "X-API-Key: $REQUESTER_KEY" \
  http://localhost:8000/api/v1/requests | jq
```

**Show:** Browse resources in Swagger UI at http://localhost:8000/docs

#### Step 2: Submit Access Request

```bash
# Request access to production database
curl -X POST http://localhost:8000/api/v1/requests \
  -H "X-API-Key: $REQUESTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_id": 1,
    "duration_seconds": 3600,
    "justification": "Need to investigate customer order discrepancy in ticket #1234",
    "is_break_glass": false
  }' | jq
```

**Explain:**
- `resource_id: 1` - prod-orders-db
- `duration_seconds: 3600` - 1 hour access
- Justification is required (minimum 10 characters)
- Returns request ID (save this!)

**Show:** If Slack is configured, notification sent to approvers

#### Step 3: View Pending Requests (as Approver)

```bash
# Set approver API key
export APPROVER_KEY="jit_your_approver_key_here"

# List pending requests
curl -H "X-API-Key: $APPROVER_KEY" \
  "http://localhost:8000/api/v1/requests?status=pending" | jq
```

**Explain:**
- Approvers see all pending requests
- Can filter by status, user, resource
- Shows justification and requester info

#### Step 4: Approve the Request

```bash
# Approve the request (replace {id} with actual request ID)
curl -X POST http://localhost:8000/api/v1/requests/6/approve \
  -H "X-API-Key: $APPROVER_KEY" | jq
```

**Explain:**
- Approver cannot approve own requests (will fail)
- Status changes to "approved"
- Slack notification sent to requester
- Audit event logged

#### Step 5: Issue Access Token

```bash
# Issue token for approved request
curl -X POST http://localhost:8000/api/v1/tokens/issue \
  -H "X-API-Key: $REQUESTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"request_id": 6}' | jq

# Save the token
export ACCESS_TOKEN="eyJ..."
```

**Explain:**
- JWT token generated with expiration
- Token includes: user ID, resource ID, scope
- Token is time-limited (1 hour in this case)

#### Step 6: Use Token to Access Protected Resource

```bash
# Access protected API endpoint
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8000/protected/api/data | jq
```

**Explain:**
- Token validated by gateway middleware
- Access granted to protected resource
- Full audit trail created

### Part 2: Break-Glass Emergency Access (15 minutes)

#### Step 1: Submit Break-Glass Request

```bash
# Submit break-glass request
curl -X POST http://localhost:8000/api/v1/requests \
  -H "X-API-Key: $REQUESTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_id": 4,
    "duration_seconds": 1800,
    "justification": "URGENT: Production API latency spike affecting customers. Incident #5678",
    "is_break_glass": true
  }' | jq
```

**Explain:**
- `is_break_glass: true` flags emergency access
- Requires dual approval (2 different approvers)
- Maximum TTL is 30 minutes for break-glass
- Security team alerted

#### Step 2: First Approval

```bash
# First approver approves
export APPROVER1_KEY="jit_approver1_key"

curl -X POST http://localhost:8000/api/v1/requests/7/approve \
  -H "X-API-Key: $APPROVER1_KEY" | jq
```

**Explain:**
- Status still "pending" - needs 2nd approval
- First approval recorded in audit log

#### Step 3: Second Approval

```bash
# Second approver (different person) approves
export APPROVER2_KEY="jit_approver2_key"

curl -X POST http://localhost:8000/api/v1/requests/7/second-approval \
  -H "X-API-Key: $APPROVER2_KEY" | jq
```

**Explain:**
- Now status changes to "approved"
- Break-glass alert sent to security team
- Enhanced audit logging activated

#### Step 4: View Break-Glass Statistics

```bash
# View break-glass stats (admin only)
export ADMIN_KEY="jit_admin_key"

curl -H "X-API-Key: $ADMIN_KEY" \
  http://localhost:8000/api/v1/break-glass/stats | jq
```

**Explain:**
- Shows all break-glass activity
- Useful for security audits
- Tracks emergency access patterns

### Part 3: Audit & Monitoring (10 minutes)

#### Step 1: View Audit Events

```bash
# List recent audit events
curl -H "X-API-Key: $ADMIN_KEY" \
  http://localhost:8000/api/v1/audit/events?limit=20 | jq
```

**Explain:**
- Complete audit trail
- Shows all actions with timestamps
- Includes IP addresses and user agents

#### Step 2: Export Audit Logs

```bash
# Export to CSV
curl -H "X-API-Key: $ADMIN_KEY" \
  "http://localhost:8000/api/v1/audit/export?start_date=2024-10-01" \
  -o audit_export.csv

# View the CSV
head -20 audit_export.csv
```

**Explain:**
- CSV export for compliance
- Filterable by date, user, resource, event type
- Immutable audit log (append-only)

#### Step 3: View Metrics

Open in browser:
- **Prometheus**: http://localhost:9090
  - Query: `jit_access_requests_total`
  - Query: `jit_http_request_duration_seconds`

- **Grafana**: http://localhost:3000 (admin/admin)
  - JIT Access Overview dashboard
  - API Performance dashboard
  - Security Monitoring dashboard

**Explain:**
- Real-time metrics
- Performance SLO tracking (p95 < 120ms)
- Alert configuration

### Part 4: Token Validation & Revocation (5 minutes)

#### Step 1: Validate Token

```bash
# Validate a token
curl -X POST http://localhost:8000/api/v1/tokens/validate \
  -H "Content-Type: application/json" \
  -d "{\"token\": \"$ACCESS_TOKEN\"}" | jq
```

**Explain:**
- Token validation without accessing resource
- Checks expiration and revocation
- Returns token claims if valid

#### Step 2: Revoke Grant

```bash
# List your active grants
curl -H "X-API-Key: $REQUESTER_KEY" \
  http://localhost:8000/api/v1/grants/me | jq

# Revoke a grant
curl -X POST http://localhost:8000/api/v1/grants/1/revoke \
  -H "X-API-Key: $REQUESTER_KEY" | jq
```

**Explain:**
- Immediate token revocation
- Token validation will fail after revocation
- Access denied at gateway

#### Step 3: Verify Revocation

```bash
# Try to use revoked token
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8000/protected/api/data
```

**Explain:**
- Returns 403 Forbidden
- "Token has been revoked" message
- Audit event logged

## Advanced Features Demo

### Policy Evaluation

```bash
# Try to exceed max TTL
curl -X POST http://localhost:8000/api/v1/requests \
  -H "X-API-Key: $REQUESTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_id": 1,
    "duration_seconds": 86400,
    "justification": "Need 24 hour access",
    "is_break_glass": false
  }'
```

**Expected:** 400 error - exceeds policy max TTL

### Self-Approval Prevention

```bash
# Try to approve own request
curl -X POST http://localhost:8000/api/v1/requests/{your_request_id}/approve \
  -H "X-API-Key: $REQUESTER_KEY"
```

**Expected:** 403 error - cannot approve own request

### Audit Statistics

```bash
# Get audit retention info
curl -H "X-API-Key: $ADMIN_KEY" \
  http://localhost:8000/api/v1/audit/retention | jq

# Get audit statistics
curl -H "X-API-Key: $ADMIN_KEY" \
  "http://localhost:8000/api/v1/audit/stats?days=7" | jq
```

## Troubleshooting

### Service Not Starting

```bash
# Check logs
docker compose logs app

# Check database connectivity
docker compose exec app python -c "from app.db import engine; engine.connect()"
```

### API Key Not Working

```bash
# Re-run seed script
docker compose exec app python scripts/seed.py

# Verify user exists
docker compose exec postgres psql -U jituser -d jitaccess -c "SELECT email, api_key FROM users;"
```

### Metrics Not Showing

```bash
# Check Prometheus targets
open http://localhost:9090/targets

# Verify metrics endpoint
curl http://localhost:8000/metrics
```

## Cleanup

```bash
# Stop all services
docker compose down

# Remove volumes (complete reset)
docker compose down -v
```

## Next Steps

1. Explore the API documentation at http://localhost:8000/docs
2. View Grafana dashboards at http://localhost:3000
3. Run load tests: `k6 run k6/load_test_scenarios.ts`
4. Configure Slack webhooks in `.env`
5. Review architecture docs in `docs/architecture.md`

