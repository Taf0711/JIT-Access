# Runbook: Token Validation Failures

## Problem

JWT tokens are failing validation, blocking access to protected resources.

## Symptoms

- Alert: "HighTokenValidationFailureRate" triggered
- Users report 403 Forbidden errors
- Gateway denying valid-looking tokens
- Increase in token validation failures metric

## Impact

- Users cannot access granted resources
- Active grants unusable
- Operational disruption
- Security concern if tokens incorrectly validated

## Investigation

### 1. Check Token Validation Metrics

```bash
# Check failure rate
curl http://localhost:8000/metrics | grep jit_token_validations_total

# Check recent validation failures
docker compose logs app | grep "TOKEN_VALIDATION_FAILED" | tail -20
```

### 2. Inspect Failing Token

```bash
# Test token validation
curl -X POST http://localhost:8000/api/v1/tokens/validate \
  -H "Content-Type: application/json" \
  -d '{"token": "failing_token_here"}' | jq

# Decode token (without validation)
echo "token_here" | cut -d. -f2 | base64 -d | jq
```

### 3. Check Common Causes

#### A. Token Expired
```bash
# Check token expiration
# In decoded token payload, check 'exp' claim
# Compare with current time: date +%s
```

#### B. Token Revoked
```bash
# Check if grant revoked
curl -H "X-API-Key: $ADMIN_KEY" \
  "http://localhost:8000/api/v1/audit/events?event_type=GRANT_REVOKED" | jq
```

#### C. JWT Secret Changed
```bash
# Check current JWT secret
docker compose exec app printenv | grep JWT_SECRET_KEY

# Compare with tokens issued before/after change
```

#### D. Clock Skew
```bash
# Check system time
docker compose exec app date
docker compose exec postgres date

# Check time drift
ntpdate -q pool.ntp.org
```

## Resolution

### Scenario 1: Expired Tokens

**Root Cause:** Token TTL expired

**Resolution:**
```bash
# User must request new token
# As user with approved request:
curl -X POST http://localhost:8000/api/v1/tokens/issue \
  -H "X-API-Key: $USER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"request_id": approved_request_id}'
```

**Prevention:**
- Monitor token expiration times
- Alert users before expiration
- Implement token refresh mechanism

### Scenario 2: Token Revoked

**Root Cause:** Grant was revoked (intentionally or by admin)

**Resolution:**
```bash
# Check why revoked
curl -H "X-API-Key: $ADMIN_KEY" \
  "http://localhost:8000/api/v1/audit/events?request_id=X" | jq

# If revoked in error, user must submit new request
```

### Scenario 3: JWT Secret Rotated

**Root Cause:** JWT_SECRET_KEY changed, invalidating all existing tokens

**Impact:** ALL tokens fail validation

**Resolution:**
```bash
# Option A: Restore previous secret (if known)
docker compose exec app sh -c 'export JWT_SECRET_KEY="old_secret" && ...'

# Option B: Accept new secret and re-issue all tokens
# 1. Announce token re-issuance required
# 2. Users re-issue tokens for active grants
# 3. Monitor re-issuance completion
```

**Prevention:**
- Document secret rotation procedure
- Maintain grace period with dual secret support
- Schedule rotations during maintenance windows

### Scenario 4: Clock Skew

**Root Cause:** System clocks out of sync

**Resolution:**
```bash
# Sync system time
docker compose exec app ntpdate -s pool.ntp.org

# Restart application
docker compose restart app

# Verify time sync
docker compose exec app date
```

**Prevention:**
- Configure NTP on all hosts
- Monitor clock drift
- Use relative time comparisons

### Scenario 5: Database Connection Issues

**Root Cause:** Cannot query grants table for revocation check

**Resolution:**
```bash
# Check database connectivity
docker compose exec app python -c "from app.db import engine; engine.connect()"

# Check database health
docker compose exec postgres pg_isready

# Restart database if needed
docker compose restart postgres

# Wait for connection pool to recover
```

## Emergency Bypass

**⚠️ Use only in emergencies**

If token validation is blocking critical operations:

```bash
# Temporarily disable revocation check
# Requires code change - not recommended

# Alternative: Issue new tokens
# Contact users to re-issue tokens from approved requests
```

## Verification

```bash
# Test token validation
TOKEN="valid_token"
curl -X POST http://localhost:8000/api/v1/tokens/validate \
  -H "Content-Type: application/json" \
  -d "{\"token\": \"$TOKEN\"}" | jq

# Expected: {"valid": true, ...}

# Test protected endpoint
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/protected/api/data | jq

# Check metrics recovery
curl http://localhost:8000/metrics | grep jit_token_validations_total
```

## Monitoring

Add these alerts:

```yaml
- alert: HighTokenValidationFailureRate
  expr: rate(jit_token_validations_total{result!="valid"}[5m]) > 0.1
  for: 2m

- alert: AllTokensFailing
  expr: rate(jit_token_validations_total{result="valid"}[5m]) == 0
  for: 1m
```

## Postmortem

1. Analyze failure pattern
2. Identify root cause
3. Update documentation
4. Improve error messages
5. Add preventive monitoring

## Related Runbooks

- [Stuck Approvals](./stuck-approvals.md)
- [Policy Update](./policy-update.md)

