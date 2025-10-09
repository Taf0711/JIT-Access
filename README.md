# JIT Access & Policy Gateway

A Just-In-Time Access Management System with policy enforcement, audit trails, and time-boxed access grants.

## Features

- 🔐 Time-boxed access requests with approval workflows
- 📋 Policy-as-code enforcement (OPA)
- 🎫 JWT-based short-lived tokens
- 📊 Prometheus metrics + Grafana dashboards
- 🔍 Complete audit trail
- 🚨 Break-glass emergency access flow
- 🔒 RBAC with requester/approver/admin roles

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)

### One-Command Startup

```bash
docker compose up -d
```

This starts all services:
- **API**: http://localhost:8000 (Swagger docs: http://localhost:8000/docs)
- **PostgreSQL**: localhost:5433 (mapped from internal 5432 to avoid conflicts)
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **OPA**: http://localhost:8181

### Seed Sample Data

```bash
docker compose exec app python scripts/seed.py
```

This creates:
- 5 users (1 admin, 2 approvers, 2 requesters)
- 10 sample resources (databases, APIs, services)
- 5 policies with TTL rules
- Sample access requests for testing

### Test the API

Use the API keys printed by the seed script:

```bash
# List access requests (as requester)
curl -H "X-API-Key: <requester-api-key>" http://localhost:8000/api/v1/requests

# Submit an access request
curl -X POST http://localhost:8000/api/v1/requests \
  -H "X-API-Key: <requester-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_id": 1,
    "duration_seconds": 3600,
    "justification": "Need to investigate customer issue #1234",
    "is_break_glass": false
  }'

# Approve a request (as approver)
curl -X POST http://localhost:8000/api/v1/requests/1/approve \
  -H "X-API-Key: <approver-api-key>"

# List your active grants
curl -H "X-API-Key: <requester-api-key>" http://localhost:8000/api/v1/grants/me
```

## Architecture

```
┌───────────────────┐       ┌────────────────────┐       ┌──────────────────┐
│  Client / UI      │ <───> │   JIT Access API   │ <───> │   PostgreSQL     │
└───────────────────┘       │   (FastAPI)        │       └──────────────────┘
                            │  - JWT Issue       │               ▲
                            │  - Approvals       │               │
                            │  - Audit Log       │               │
                            └─────────▲──────────┘               │
                                      │                          │
                           ┌──────────┴───────────┐      ┌───────┴──────┐
                           │   Policy Engine      │      │    Redis     │
                           │   (OPA with Rego)    │      │  TTL, cache  │
                           └──────────▲───────────┘      └──────────────┘
                                      │
                              ┌───────┴─────────┐
                              │  Demo Gateway   │  ← protects sample API
                              │  (middleware)   │
                              └─────────────────┘
```

## Development

### Local Setup (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env

# Run PostgreSQL and Redis (via Docker)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=jitpass -e POSTGRES_USER=jituser -e POSTGRES_DB=jitaccess postgres:15-alpine
docker run -d -p 6379:6379 redis:7-alpine

# Run migrations
alembic upgrade head

# Seed data
python scripts/seed.py

# Start API server
uvicorn app.main:app --reload --port 8000
```

### Run Tests

```bash
pytest tests/ -v
```

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

- `POST /api/v1/requests` - Submit access request
- `GET /api/v1/requests` - List requests
- `POST /api/v1/requests/{id}/approve` - Approve request
- `POST /api/v1/requests/{id}/deny` - Deny request
- `GET /api/v1/grants/me` - List active grants
- `POST /api/v1/tokens/issue` - Issue JWT token (Week 2)
- `GET /api/v1/audit/export` - Export audit logs (Week 4)

## Monitoring

### Grafana Dashboards

Access Grafana at http://localhost:3000 (admin/admin)

Dashboards include:
- **JIT Access Overview**: Request rates, approval metrics, active grants
- **API Performance**: p50/p95/p99 latency by endpoint
- **Security Monitoring**: Denied requests, token failures, break-glass usage

### Metrics

Prometheus metrics at http://localhost:9090

Key metrics:
- `access_requests_total{status, resource_type}`
- `approval_duration_seconds` (histogram)
- `active_grants_total`
- `token_validations_total{result}`
- `http_request_duration_seconds{endpoint, method}`

## Security

- API key authentication (stub - replace with OAuth2/OIDC in production)
- JWT tokens with expiration
- Policy-as-code enforcement via OPA
- Complete audit trail (append-only)
- RBAC with role-based permissions
- Break-glass emergency access with dual approval

## Project Status

- ✅ Week 1: Core flows & foundation
- 🚧 Week 2: Policy engine & enforcement (in progress)
- ⏳ Week 3: Observability & operations
- ⏳ Week 4: Hardening & polish

## Documentation

- [Architecture Details](docs/architecture.md)
- [Demo Script](docs/demo-script.md)
- [Runbooks](docs/runbooks/)
- [Load Test Results](docs/load-test-results.md)

## License

MIT
