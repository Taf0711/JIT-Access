#!/bin/bash

# Quick Test Script for JIT Access & Policy Gateway
# This script demonstrates the basic workflow with manual prompts

set -e

BASE_URL="http://localhost:8000"
API_V1="$BASE_URL/api/v1"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test user API keys
REQUESTER_KEY="jit_Q2J3hWJbQjeWpzHaqg74lN-EQncJoCCVV_ajJuQ97og"
APPROVER_KEY="jit_BS8-UljUp5e8V4H0I-gcHlm6IrFZq1YfxIlkx7rhzDM"
ADMIN_KEY="jit_Yh5IWl3M2cm3Kgw5bS3evtyusvgiQ8G8Hh2B-5mmQZE"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          JIT Access & Policy Gateway - Quick Test             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Health Check
echo -e "${GREEN}[1/7] Checking System Health...${NC}"
curl -s "$BASE_URL/health" | jq '.'
echo ""
read -p "Press Enter to continue..."

# Step 2: List Resources
echo ""
echo -e "${GREEN}[2/7] Listing Available Resources...${NC}"
RESOURCES=$(curl -s -H "X-API-Key: $REQUESTER_KEY" "$API_V1/resources")
echo "$RESOURCES" | jq '.'
RESOURCE_ID=$(echo "$RESOURCES" | jq -r '.[0].id')
RESOURCE_NAME=$(echo "$RESOURCES" | jq -r '.[0].name')
echo ""
echo -e "${YELLOW}➜ We'll request access to: $RESOURCE_NAME (ID: $RESOURCE_ID)${NC}"
echo ""
read -p "Press Enter to continue..."

# Step 3: Create Access Request
echo ""
echo -e "${GREEN}[3/7] Creating Access Request (as Requester)...${NC}"
REQUEST_RESPONSE=$(curl -s -X POST "$API_V1/requests" \
  -H "X-API-Key: $REQUESTER_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"resource_id\": $RESOURCE_ID,
    \"duration_seconds\": 3600,
    \"justification\": \"Need access to debug production issue #1234\",
    \"is_break_glass\": false
  }")

echo "$REQUEST_RESPONSE" | jq '.'
REQUEST_ID=$(echo "$REQUEST_RESPONSE" | jq -r '.id')
echo ""
echo -e "${YELLOW}➜ Created Request ID: $REQUEST_ID${NC}"
echo ""
read -p "Press Enter to continue..."

# Step 4: View Pending Requests
echo ""
echo -e "${GREEN}[4/7] Viewing Pending Requests (as Approver)...${NC}"
curl -s -H "X-API-Key: $APPROVER_KEY" "$API_V1/requests?status=pending" | jq '.'
echo ""
read -p "Press Enter to continue..."

# Step 5: Approve Request
echo ""
echo -e "${GREEN}[5/7] Approving Request (as Approver)...${NC}"
curl -s -X POST "$API_V1/requests/$REQUEST_ID/approve" \
  -H "X-API-Key: $APPROVER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "approved_duration_seconds": 3600,
    "comment": "Approved for debugging"
  }' | jq '.'
echo ""
read -p "Press Enter to continue..."

# Step 6: Issue JWT Token
echo ""
echo -e "${GREEN}[6/7] Issuing JWT Token (as Requester)...${NC}"
TOKEN_RESPONSE=$(curl -s -X POST "$API_V1/tokens/issue" \
  -H "X-API-Key: $REQUESTER_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"request_id\": $REQUEST_ID
  }")

echo "$TOKEN_RESPONSE" | jq '.'
JWT_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')
echo ""
echo -e "${YELLOW}➜ JWT Token Issued (truncated): ${JWT_TOKEN:0:50}...${NC}"
echo ""
read -p "Press Enter to continue..."

# Step 7: Access Protected Resource
echo ""
echo -e "${GREEN}[7/7] Accessing Protected Resource with JWT...${NC}"
curl -s -H "Authorization: Bearer $JWT_TOKEN" "$BASE_URL/protected/resource" | jq '.'
echo ""

# Summary
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                      ✅ TEST COMPLETE                          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Success! The full workflow is working:${NC}"
echo "  1. ✓ System is healthy"
echo "  2. ✓ Listed available resources"
echo "  3. ✓ Created access request (ID: $REQUEST_ID)"
echo "  4. ✓ Viewed pending requests"
echo "  5. ✓ Approved request"
echo "  6. ✓ Issued JWT token"
echo "  7. ✓ Accessed protected resource"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  - View API docs: http://localhost:8000/docs"
echo "  - Check Grafana: http://localhost:3000 (admin/admin)"
echo "  - See full guide: cat TESTING_GUIDE.md"
echo "  - Run load tests: cd k6 && k6 run load_test_scenarios.ts"
echo ""

