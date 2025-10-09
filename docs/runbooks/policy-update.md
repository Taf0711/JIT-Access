# Runbook: Policy Updates

## Problem

Need to update access policies (max TTL, approval rules, time windows).

## When to Update Policies

- Change in security requirements
- New compliance rules
- Resource classification changes
- Incident response (tighten access)
- Policy violation patterns detected

## Policy Types

1. **TTL Policies** - Maximum access duration
2. **Approval Policies** - Who can approve, how many approvers
3. **Time Window Policies** - When access is allowed
4. **Break-Glass Policies** - Emergency access rules

## Pre-Update Checklist

- [ ] Document current policy configuration
- [ ] Get approval from security team
- [ ] Plan for active grants (do they get revoked?)
- [ ] Schedule change window
- [ ] Notify affected users
- [ ] Backup current policies

## Update Procedures

### 1. Update Max TTL

**Scenario:** Reduce max access duration for sensitive resource

```bash
# Get current policy
curl -H "X-API-Key: $ADMIN_KEY" \
  http://localhost:8000/api/v1/audit/events | jq '.[] | select(.resource_id==2)'

# Update via SQL (no API endpoint yet)
docker compose exec postgres psql -U jituser -d jitaccess -c "
UPDATE policies 
SET max_ttl_seconds = 1800  -- 30 minutes
WHERE resource_id = 2;      -- prod-users-db (PII data)
"

# Verify
docker compose exec postgres psql -U jituser -d jitaccess -c "
SELECT resource_id, name, max_ttl_seconds/60 as max_minutes 
FROM policies WHERE resource_id = 2;
"
```

**Impact:**
- New requests limited to new TTL
- Existing grants unchanged (until expiration)
- OPA will enforce new limit immediately

### 2. Add Time Window Restrictions

**Scenario:** No production access on weekends

```bash
# Update policy
docker compose exec postgres psql -U jituser -d jitaccess -c "
UPDATE policies 
SET time_window_restrictions = '{\"no_access_days\": [5, 6], \"business_hours_only\": true}'::json
WHERE resource_id = 4;  -- prod-api
"
```

**JSON Structure:**
```json
{
  "no_access_days": [5, 6],  // Saturday=5, Sunday=6
  "business_hours_only": true,
  "allowed_hours": {
    "start": 9,
    "end": 17
  }
}
```

### 3. Change Approval Requirements

**Scenario:** Require dual approval for all production resources

```bash
# Update approval rules
docker compose exec postgres psql -U jituser -d jitaccess -c "
UPDATE policies 
SET approval_rules = '{\"min_approvers\": 2, \"allowed_roles\": [\"approver\", \"admin\"]}'::json
WHERE resource_id IN (
  SELECT id FROM resources WHERE metadata->>'environment' = 'production'
);
"
```

**Impact:**
- Existing pending requests need re-evaluation
- May need additional approvals

### 4. Update OPA Policies

**Scenario:** Add new policy rules

```bash
# Edit policies/access_policy.rego
vim policies/access_policy.rego

# Example: Add IP allowlist
# Add to Rego file:
# check_ip_allowlist if {
#     input.request.ip_address
#     allowed_ips := ["10.0.0.0/8", "192.168.0.0/16"]
#     # IP validation logic
# }

# Restart OPA to reload policies
docker compose restart opa

# Verify OPA health
curl http://localhost:8181/health
```

### 5. Bulk Policy Update

**Scenario:** Update all policies based on resource type

```bash
# Tighten all database access
docker compose exec postgres psql -U jituser -d jitaccess -c "
UPDATE policies p
SET max_ttl_seconds = 3600,  -- 1 hour max
    approval_rules = '{\"min_approvers\": 1, \"requires_justification\": true}'::json
FROM resources r
WHERE p.resource_id = r.id 
  AND r.type = 'database'
  AND r.metadata->>'environment' = 'production';
"
```

## Handle Active Grants

### Option 1: Grandfather Existing Grants

**Default behavior** - active grants continue until expiration

```bash
# No action needed
# Grants issued under old policy remain valid
```

### Option 2: Revoke Non-Compliant Grants

**Use for security incidents**

```bash
# Find grants exceeding new policy
docker compose exec postgres psql -U jituser -d jitaccess -c "
SELECT g.id, g.request_id, ar.duration_seconds, p.max_ttl_seconds
FROM grants g
JOIN access_requests ar ON g.request_id = ar.id
JOIN policies p ON ar.resource_id = p.resource_id
WHERE ar.duration_seconds > p.max_ttl_seconds
  AND g.expires_at > NOW()
  AND g.revoked = false;
"

# Revoke via API
for grant_id in $(list_of_grant_ids); do
  curl -X POST http://localhost:8000/api/v1/grants/$grant_id/revoke \
    -H "X-API-Key: $ADMIN_KEY"
done
```

### Option 3: Notify and Schedule Revocation

```bash
# Send notifications to affected users
# Give 24-hour warning
# Schedule revocation
```

## Testing

### 1. Test Policy Evaluation

```bash
# Try to create request that violates new policy
curl -X POST http://localhost:8000/api/v1/requests \
  -H "X-API-Key: $REQUESTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_id": 2,
    "duration_seconds": 7200,  # Should exceed new limit
    "justification": "Test policy enforcement"
  }'

# Expected: 400 error with policy violation message
```

### 2. Test Time Windows

```bash
# If testing on weekend with no_access_days policy:
curl -X POST http://localhost:8000/api/v1/requests \
  -H "X-API-Key: $REQUESTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_id": 4,
    "duration_seconds": 3600,
    "justification": "Test weekend restriction"
  }'

# Expected: 400 error - access not allowed on weekends
```

### 3. Verify OPA Integration

```bash
# Query OPA directly
curl -X POST http://localhost:8181/v1/data/jit/access/allow_request \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "request": {
        "duration_seconds": 7200,
        "resource_id": 2
      },
      "policy": {
        "max_ttl_seconds": 3600
      }
    }
  }' | jq
```

## Rollback

If policy update causes issues:

```bash
# Restore from backup
docker compose exec postgres psql -U jituser -d jitaccess < policy_backup.sql

# Or manual rollback
docker compose exec postgres psql -U jituser -d jitaccess -c "
UPDATE policies 
SET max_ttl_seconds = 7200,  -- old value
    approval_rules = '{\"min_approvers\": 1}'::json  -- old value
WHERE resource_id = 2;
"

# Restart services
docker compose restart app opa
```

## Documentation

After policy update:

1. Update policy documentation
2. Notify stakeholders
3. Add audit log entry
4. Update runbooks if needed
5. Review impact in next security meeting

## Monitoring

Watch these metrics after policy changes:

```bash
# Policy evaluation metrics
curl http://localhost:8000/metrics | grep jit_policy_evaluations_total

# Policy violation rate
curl http://localhost:8000/metrics | grep jit_policy_violations_total

# Request denial rate
curl http://localhost:8000/metrics | grep 'jit_approvals_total.*denied'
```

## Related Runbooks

- [Stuck Approvals](./stuck-approvals.md)
- [Token Failures](./token-failures.md)

