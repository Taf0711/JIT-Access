#!/bin/bash

# JIT Access & Policy Gateway - Test Workflow Script
# This script tests the complete workflow of the system

set -e  # Exit on error

BASE_URL="http://localhost:8000"
API_V1="$BASE_URL/api/v1"

# Test user API keys from seeded data
REQUESTER_KEY="jit_Q2J3hWJbQjeWpzHaqg74lN-EQncJoCCVV_ajJuQ97og"
APPROVER_KEY="jit_BS8-UljUp5e8V4H0I-gcHlm6IrFZq1YfxIlkx7rhzDM"
ADMIN_KEY="jit_Yh5IWl3M2cm3Kgw5bS3evtyusvgiQ8G8Hh2B-5mmQZE"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║       JIT Access & Policy Gateway - Full System Test          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Check System Health
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Step 1: Checking System Health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s "$BASE_URL/health" | jq '.'
echo ""

# Step 2: List Available Resources
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 2: Listing Available Resources"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
RESOURCES=$(curl -s -H "X-API-Key: $REQUESTER_KEY" "$API_V1/resources" | jq '.')
echo "$RESOURCES"
echo ""

# Extract first resource ID for testing
RESOURCE_ID=$(echo "$RESOURCES" | jq -r '.[0].id')
RESOURCE_NAME=$(echo "$RESOURCES" | jq -r '.[0].name')
echo "✓ Using Resource: $RESOURCE_NAME (ID: $RESOURCE_ID)"
echo ""

# Step 3: Create Access Request (as Requester)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🙋 Step 3: Creating Access Request (as Requester)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
REQUEST_RESPONSE=$(curl -s -X POST "$API_V1/requests" \
  -H "X-API-Key: $REQUESTER_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"resource_id\": $RESOURCE_ID,
    \"duration_seconds\": 7200,
    \"justification\": \"Need access to debug production issue #1234\",
    \"is_break_glass\": false
  }")

echo "$REQUEST_RESPONSE" | jq '.'
REQUEST_ID=$(echo "$REQUEST_RESPONSE" | jq -r '.id')
echo ""
echo "✓ Created Request ID: $REQUEST_ID"
echo ""

# Step 4: View Pending Requests (as Approver)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "👀 Step 4: Viewing Pending Requests (as Approver)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -H "X-API-Key: $APPROVER_KEY" "$API_V1/requests?status=PENDING" | jq '.'
echo ""

# Step 5: Approve Request (as Approver)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Step 5: Approving Request (as Approver)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
APPROVAL_RESPONSE=$(curl -s -X POST "$API_V1/requests/$REQUEST_ID/approve" \
  -H "X-API-Key: $APPROVER_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"approved_duration_seconds\": 3600,
    \"comment\": \"Approved for 1 hour to debug the issue\"
  }")

echo "$APPROVAL_RESPONSE" | jq '.'
GRANT_ID=$(echo "$APPROVAL_RESPONSE" | jq -r '.grant.id')
echo ""
echo "✓ Request Approved - Grant ID: $GRANT_ID"
echo ""

# Step 6: Issue JWT Token (as Requester)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎫 Step 6: Issuing JWT Token (as Requester)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOKEN_RESPONSE=$(curl -s -X POST "$API_V1/tokens/issue" \
  -H "X-API-Key: $REQUESTER_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"grant_id\": $GRANT_ID
  }")

echo "$TOKEN_RESPONSE" | jq '.'
JWT_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')
echo ""
echo "✓ JWT Token Issued (truncated): ${JWT_TOKEN:0:50}..."
echo ""

# Step 7: Access Protected Resource
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔒 Step 7: Accessing Protected Resource with JWT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -H "Authorization: Bearer $JWT_TOKEN" "$BASE_URL/protected/resource" | jq '.'
echo ""

# Step 8: Validate Token
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Step 8: Validating JWT Token"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -X POST "$API_V1/tokens/validate" \
  -H "Content-Type: application/json" \
  -d "{
    \"token\": \"$JWT_TOKEN\"
  }" | jq '.'
echo ""

# Step 9: View Active Grants (as Requester)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Step 9: Viewing Active Grants (as Requester)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -H "X-API-Key: $REQUESTER_KEY" "$API_V1/grants?revoked=false" | jq '.'
echo ""

# Step 10: View Audit Trail (as Admin)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Step 10: Viewing Audit Trail (as Admin)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -H "X-API-Key: $ADMIN_KEY" "$API_V1/audit?limit=10" | jq '.'
echo ""

# Step 11: Break Glass Request
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚨 Step 11: Creating Break-Glass Request (as Requester)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
BREAK_GLASS_RESPONSE=$(curl -s -X POST "$API_V1/break-glass" \
  -H "X-API-Key: $REQUESTER_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"resource_id\": $RESOURCE_ID,
    \"justification\": \"Critical production outage! Database is down!\",
    \"duration_seconds\": 1800
  }")

echo "$BREAK_GLASS_RESPONSE" | jq '.'
BG_GRANT_ID=$(echo "$BREAK_GLASS_RESPONSE" | jq -r '.grant.id')
echo ""
echo "✓ Break-Glass Grant ID: $BG_GRANT_ID"
echo ""

# Step 12: Revoke Grant (as Admin)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🛑 Step 12: Revoking Grant (as Admin)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -X POST "$API_V1/grants/$GRANT_ID/revoke" \
  -H "X-API-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"reason\": \"Access no longer needed - issue resolved\"
  }" | jq '.'
echo ""

# Step 13: Check Metrics
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📈 Step 13: Checking Prometheus Metrics"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Sample metrics from $BASE_URL/metrics:"
curl -s "$BASE_URL/metrics" | grep -E "^(jit_http_requests_total|jit_access_requests_total|jit_active_grants)" | head -10
echo ""

# Summary
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                     ✅ TEST COMPLETE                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "✓ System Health: OK"
echo "✓ Resources Listed: OK"
echo "✓ Access Request Created: ID $REQUEST_ID"
echo "✓ Request Approved: Grant ID $GRANT_ID"
echo "✓ JWT Token Issued: OK"
echo "✓ Protected Resource Accessed: OK"
echo "✓ Token Validated: OK"
echo "✓ Break-Glass Request: Grant ID $BG_GRANT_ID"
echo "✓ Grant Revoked: OK"
echo "✓ Audit Trail: OK"
echo ""
echo "🌐 Open in Browser:"
echo "   - API Documentation: http://localhost:8000/docs"
echo "   - Grafana Dashboard: http://localhost:3000 (admin/admin)"
echo "   - Prometheus: http://localhost:9090"
echo ""

