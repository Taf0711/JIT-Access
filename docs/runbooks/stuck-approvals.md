# Runbook: Stuck Approvals

## Problem

Access requests are pending for extended periods without approval.

## Symptoms

- Alert: "HighApprovalLatency" triggered
- Requests in pending state > 5 minutes
- User complaints about delays
- Slack notifications not being sent

## Impact

- User productivity blocked
- Emergency access delayed
- SLO breach (approval time > 5 min)

## Investigation

### 1. Check Pending Requests

```bash
# List all pending requests
curl -H "X-API-Key: $ADMIN_KEY" \
  "http://localhost:8000/api/v1/requests?status=pending&limit=50" | jq

# Check for break-glass requests
curl -H "X-API-Key: $ADMIN_KEY" \
  "http://localhost:8000/api/v1/requests?status=pending&is_break_glass=true" | jq
```

### 2. Check Notification System

```bash
# Verify Slack webhook configured
docker compose exec app printenv | grep SLACK_WEBHOOK_URL

# Check application logs for notification errors
docker compose logs app | grep -i "slack\|notification"
```

### 3. Check Approver Availability

```bash
# List approvers
docker compose exec postgres psql -U jituser -d jitaccess \
  -c "SELECT id, email, role FROM users WHERE role IN ('approver', 'admin');"

# Check if approvers have been notified
curl -H "X-API-Key: $ADMIN_KEY" \
  "http://localhost:8000/api/v1/audit/events?event_type=REQUEST_CREATED&limit=20" | jq
```

## Resolution

### Option 1: Manual Approval (Immediate)

```bash
# As admin, directly approve critical requests
export ADMIN_KEY="your_admin_key"
export REQUEST_ID="pending_request_id"

curl -X POST http://localhost:8000/api/v1/requests/$REQUEST_ID/approve \
  -H "X-API-Key: $ADMIN_KEY"
```

**When to use:** Emergency situations, break-glass requests

### Option 2: Escalate to On-Call Approver

1. Check on-call rotation
2. Contact on-call approver directly (phone/Slack DM)
3. Have them approve via API or Swagger UI

### Option 3: Fix Notification System

```bash
# Add Slack webhook URL
echo "SLACK_WEBHOOK_URL=https://hooks.slack.com/..." >> .env

# Restart application
docker compose restart app

# Test notification
curl -X POST http://localhost:8000/api/v1/requests \
  -H "X-API-Key: $REQUESTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"resource_id": 1, "duration_seconds": 3600, "justification": "Test notification", "is_break_glass": false}'
```

### Option 4: Temporarily Increase Admin Coverage

```bash
# Promote an approver to admin temporarily
docker compose exec postgres psql -U jituser -d jitaccess \
  -c "UPDATE users SET role='admin' WHERE email='trusted_approver@example.com';"

# Remember to demote after incident
# UPDATE users SET role='approver' WHERE email='trusted_approver@example.com';
```

## Prevention

1. **Set up monitoring alerts**
   - Alert on pending requests > 5 minutes
   - Alert on failed Slack notifications

2. **Implement approval SLA**
   - Target: < 5 minutes for standard requests
   - Target: < 2 minutes for break-glass

3. **On-call rotation**
   - Designate on-call approvers
   - Include in PagerDuty/Opsgenie

4. **Auto-escalation**
   - After 10 minutes, notify on-call
   - After 30 minutes, auto-approve low-risk requests

5. **Backup notification channels**
   - Email notifications as fallback
   - SMS for break-glass requests

## Verification

```bash
# Verify resolution
curl -H "X-API-Key: $ADMIN_KEY" \
  "http://localhost:8000/api/v1/requests?status=pending" | jq length

# Check approval latency metrics
curl http://localhost:8000/metrics | grep jit_approval_duration

# Verify Grafana dashboard
open http://localhost:3000/d/jit-overview
```

## Postmortem Actions

1. Review approval logs
2. Identify bottlenecks
3. Update on-call procedures
4. Improve notification reliability
5. Document lessons learned

## Related Runbooks

- [Token Failures](./token-failures.md)
- [Policy Update](./policy-update.md)

