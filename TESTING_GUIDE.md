# 🧪 Practical Testing Guide

This guide provides step-by-step instructions to manually test the JIT Access & Policy Gateway.

## Prerequisites

1. Ensure all Docker containers are running:
   ```bash
   docker compose ps
   ```

2. Seed the database with test data:
   ```bash
   docker compose exec app python scripts/seed.py
   ```

## Test Users & API Keys

| Role | Email | API Key |
|------|-------|---------|
| Requester | requester1@example.com | `jit_Q2J3hWJbQjeWpzHaqg74lN-EQncJoCCVV_ajJuQ97og` |
| Approver | approver1@example.com | `jit_BS8-UljUp5e8V4H0I-gcHlm6IrFZq1YfxIlkx7rhzDM` |
| Admin | admin@example.com | `jit_Yh5IWl3M2cm3Kgw5bS3evtyusvgiQ8G8Hh2B-5mmQZE` |

---

## Testing Workflow

### 1. Check System Health

```bash
curl -s http://localhost:8000/health | jq '.'
```

Expected output:
```json
{
  "status": "healthy",
  "service": "jit-access"
}
```

---

### 2. List Available Resources

```bash
curl -s http://localhost:8000/api/v1/resources \
  -H "X-API-Key: jit_Q2J3hWJbQjeWpzHaqg74lN-EQncJoCCVV_ajJuQ97og" | jq '.'
```

You should see a list of 10 resources including databases, APIs, and services.

**Save a resource ID for later steps** (e.g., `"id": 1`)

---

### 3. Create an Access Request

```bash
curl -s -X POST http://localhost:8000/api/v1/requests \
  -H "X-API-Key: jit_Q2J3hWJbQjeWpzHaqg74lN-EQncJoCCVV_ajJuQ97og" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_id": 1,
    "duration_seconds": 3600,
    "justification": "Need to debug production issue #1234",
    "is_break_glass": false
  }' | jq '.'
```

Expected: You'll get a request with `"status": "pending"`. **Save the `"id"` value** (e.g., `REQUEST_ID=6`).

---

### 4. View Pending Requests (as Approver)

```bash
curl -s http://localhost:8000/api/v1/requests?status=pending \
  -H "X-API-Key: jit_BS8-UljUp5e8V4H0I-gcHlm6IrFZq1YfxIlkx7rhzDM" | jq '.'
```

You should see your pending request in the list.

---

### 5. Approve the Request

Replace `<REQUEST_ID>` with the ID from step 3:

```bash
curl -s -X POST http://localhost:8000/api/v1/requests/<REQUEST_ID>/approve \
  -H "X-API-Key: jit_BS8-UljUp5e8V4H0I-gcHlm6IrFZq1YfxIlkx7rhzDM" \
  -H "Content-Type: application/json" \
  -d '{
    "approved_duration_seconds": 3600,
    "comment": "Approved for 1 hour"
  }' | jq '.'
```

Expected: The request status changes to `"status": "approved"`.

---

### 6. Issue a JWT Token

```bash
curl -s -X POST http://localhost:8000/api/v1/tokens/issue \
  -H "X-API-Key: jit_Q2J3hWJbQjeWpzHaqg74lN-EQncJoCCVV_ajJuQ97og" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": <REQUEST_ID>
  }' | jq '.'
```

Expected: You'll receive a JWT token. **Save the `"access_token"` value** for the next step.

---

### 7. Access a Protected Resource

Replace `<JWT_TOKEN>` with the token from step 6:

```bash
curl -s http://localhost:8000/protected/resource \
  -H "Authorization: Bearer <JWT_TOKEN>" | jq '.'
```

Expected output:
```json
{
  "message": "Access granted to protected resource",
  "user_id": 4,
  "resource_id": 1,
  "resource_name": "prod-orders-db",
  "expires_at": "2025-10-09T20:15:44.123456Z"
}
```

---

### 8. Validate the Token

```bash
curl -s -X POST http://localhost:8000/api/v1/tokens/validate \
  -H "Content-Type: application/json" \
  -d '{
    "token": "<JWT_TOKEN>"
  }' | jq '.'
```

Expected: Shows token validity, user info, resource info, and expiration.

---

### 9. Test Break-Glass Access

Break-glass access is instant and doesn't require approval:

```bash
curl -s -X POST http://localhost:8000/api/v1/break-glass \
  -H "X-API-Key: jit_Q2J3hWJbQjeWpzHaqg74lN-EQncJoCCVV_ajJuQ97og" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_id": 1,
    "justification": "CRITICAL: Production database is down! Need immediate access!",
    "duration_seconds": 1800
  }' | jq '.'
```

Expected: Instant approval with a grant. **This triggers alerts** and is logged prominently in audit trail.

---

### 10. View Audit Trail (Admin)

```bash
curl -s http://localhost:8000/api/v1/audit?limit=20 \
  -H "X-API-Key: jit_Yh5IWl3M2cm3Kgw5bS3evtyusvgiQ8G8Hh2B-5mmQZE" | jq '.'
```

You should see all the events from your testing: request created, approved, token issued, etc.

---

### 11. List Active Grants

```bash
curl -s http://localhost:8000/api/v1/grants \
  -H "X-API-Key: jit_Q2J3hWJbQjeWpzHaqg74lN-EQncJoCCVV_ajJuQ97og" | jq '.'
```

You should see your active grants with expiration times.

---

### 12. Revoke a Grant (Admin)

Replace `<GRANT_ID>` with an ID from step 11:

```bash
curl -s -X POST http://localhost:8000/api/v1/grants/<GRANT_ID>/revoke \
  -H "X-API-Key: jit_Yh5IWl3M2cm3Kgw5bS3evtyusvgiQ8G8Hh2B-5mmQZE" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Access no longer needed - issue resolved"
  }' | jq '.'
```

Expected: The grant is revoked and the JWT token will no longer work.

---

### 13. Export Audit Log as CSV

```bash
curl -s http://localhost:8000/api/v1/audit/export?format=csv \
  -H "X-API-Key: jit_Yh5IWl3M2cm3Kgw5bS3evtyusvgiQ8G8Hh2B-5mmQZE" \
  > audit_log.csv

head audit_log.csv
```

---

## Web UIs to Explore

### 1. API Documentation (Swagger UI)
- **URL**: http://localhost:8000/docs
- Try out all the endpoints interactively
- Click "Authorize" and enter an API key to test authenticated endpoints

### 2. Grafana Dashboard
- **URL**: http://localhost:3000
- **Login**: `admin` / `admin`
- View metrics dashboards for:
  - HTTP request rates and latencies
  - Access request metrics
  - Active grants
  - Break-glass events

### 3. Prometheus Metrics
- **URL**: http://localhost:9090
- Query custom metrics:
  - `jit_http_requests_total` - Total HTTP requests
  - `jit_access_requests_total` - Access requests by status
  - `jit_active_grants_total` - Number of active grants
  - `jit_break_glass_events_total` - Break-glass access count
  - `jit_tokens_issued_total` - JWT tokens issued
  - `jit_token_validations_total` - Token validation attempts

### 4. Raw Metrics Endpoint
- **URL**: http://localhost:8000/metrics
- See Prometheus-format metrics in plain text

---

## Load Testing

### Run k6 Load Tests

```bash
cd k6
k6 run load_test_scenarios.ts
```

This will simulate:
- Multiple users requesting access
- Approvers processing requests
- Token issuance and validation
- Protected resource access
- Break-glass scenarios

---

## Troubleshooting

### Check Container Logs

```bash
# App logs
docker compose logs -f app

# Postgres logs
docker compose logs postgres

# OPA logs
docker compose logs opa

# Redis logs
docker compose logs redis
```

### Restart Everything

```bash
docker compose down
docker compose up -d
```

### Check Database

```bash
docker compose exec postgres psql -U jituser -d jitaccess

# List users
SELECT id, email, role FROM users;

# List access requests
SELECT id, user_id, resource_id, status, is_break_glass FROM access_requests;

# List grants
SELECT id, request_id, expires_at, revoked FROM grants;
```

---

## Key Concepts Demonstrated

1. **Just-In-Time Access**: Users request time-limited access, not permanent permissions
2. **Approval Workflow**: Requests require approval from authorized approvers
3. **JWT Gateway**: Issued tokens grant temporary access to protected resources
4. **Break-Glass**: Emergency access for critical situations (auto-approved, heavily audited)
5. **Audit Trail**: Immutable log of all access events
6. **Policy Enforcement**: OPA policies validate requests and enforce rules
7. **Observability**: Prometheus metrics + Grafana dashboards for monitoring
8. **Revocation**: Grants can be revoked before expiration

---

## Next Steps

- Modify policies in `policies/access_policy.rego` and reload OPA
- Create custom Grafana dashboards
- Set up Slack notifications (configure `SLACK_WEBHOOK_URL`)
- Run the full test workflow: `./test-workflow.sh`
- Explore the codebase in `/app` directory

