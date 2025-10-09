# JIT Access System Architecture

## Overview

The JIT (Just-In-Time) Access & Policy Gateway is a comprehensive access management system that provides time-boxed, policy-enforced access to critical resources with complete audit trails.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │   Web    │  │   CLI    │  │  Slack   │  │  Mobile  │       │
│  │   UI     │  │  Client  │  │  Bot     │  │   App    │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       └──────────────┴──────────────┴─────────────┘             │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS/REST API
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Gateway Layer                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              FastAPI Application                          │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │  │
│  │  │  Request   │  │   Token    │  │   Audit    │        │  │
│  │  │   API      │  │    API     │  │    API     │        │  │
│  │  └────────────┘  └────────────┘  └────────────┘        │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │  │
│  │  │   Grant    │  │Break-Glass │  │  Metrics   │        │  │
│  │  │    API     │  │    API     │  │    API     │        │  │
│  │  └────────────┘  └────────────┘  └────────────┘        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                     │
│  ┌────────────────────────┼─────────────────────────────────┐  │
│  │      Middleware Layer  │                                  │  │
│  │  ┌─────────────────────┴─────────┐  ┌─────────────────┐ │  │
│  │  │    Gateway Auth Middleware    │  │  Metrics        │ │  │
│  │  │  (JWT Token Validation)       │  │  Middleware     │ │  │
│  │  └───────────────────────────────┘  └─────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────┬──────────────┬──────────────┬──────────────┬───────┘
            │              │              │              │
            ▼              ▼              ▼              ▼
┌────────────────┐  ┌────────────┐  ┌──────────┐  ┌──────────┐
│   PostgreSQL   │  │    Redis   │  │   OPA    │  │  Slack   │
│   (Primary     │  │  (Cache/   │  │ (Policy  │  │ (Notif.) │
│    Store)      │  │   TTL)     │  │  Engine) │  │          │
└────────────────┘  └────────────┘  └──────────┘  └──────────┘
            │                              │
            ▼                              ▼
┌────────────────────────────────────────────────────────┐
│             Observability Stack                        │
│  ┌──────────────┐       ┌──────────────┐             │
│  │  Prometheus  │◄──────┤   Grafana    │             │
│  │  (Metrics)   │       │ (Dashboard)  │             │
│  └──────────────┘       └──────────────┘             │
└────────────────────────────────────────────────────────┘
```

## Core Components

### 1. API Layer

**FastAPI Application**
- REST API endpoints for all operations
- OpenAPI/Swagger documentation
- Pydantic models for validation
- SQLAlchemy ORM for database access

**Key Endpoints:**
- `/api/v1/requests` - Access request management
- `/api/v1/tokens` - JWT token issuance/validation
- `/api/v1/grants` - Active grant management
- `/api/v1/audit` - Audit log access and export
- `/api/v1/break-glass` - Emergency access flows
- `/metrics` - Prometheus metrics

### 2. Authentication & Authorization

**API Key Authentication**
- Simple API key-based auth (stub for development)
- Header-based: `X-API-Key: <key>`
- Production: Replace with OAuth2/OIDC

**RBAC (Role-Based Access Control)**
- Roles: `requester`, `approver`, `admin`
- Hierarchical permissions
- Admin has all permissions

**JWT Tokens**
- Short-lived access tokens
- HS256 signing (configurable to RS256)
- Claims: user_id, resource_id, scope, expiration
- Token validation at gateway

### 3. Policy Engine (OPA)

**Open Policy Agent Integration**
- Rego-based policy rules
- Real-time policy evaluation
- Policies enforced:
  - Maximum TTL validation
  - Time window restrictions
  - Approver eligibility
  - Break-glass requirements (dual approval)

**Policy Decisions:**
- Request validation
- Approval authorization
- Resource access checks

### 4. Data Layer

**PostgreSQL Schema:**

```sql
Users
├── id (PK)
├── email
├── name
├── role (requester/approver/admin)
└── api_key

Resources
├── id (PK)
├── name
├── type (database/api/server/service)
├── description
└── resource_metadata (JSON)

Policies
├── id (PK)
├── resource_id (FK)
├── max_ttl_seconds
├── approval_rules (JSON)
└── time_window_restrictions (JSON)

AccessRequests
├── id (PK)
├── user_id (FK)
├── resource_id (FK)
├── duration_seconds
├── justification
├── status (pending/approved/denied)
├── is_break_glass
├── approved_by (FK)
└── timestamps

Grants
├── id (PK)
├── request_id (FK)
├── token_hash (SHA256)
├── expires_at
├── revoked
└── timestamps

AuditEvents (Append-only)
├── id (PK)
├── event_type
├── user_id (FK)
├── resource_id (FK)
├── request_id (FK)
├── event_metadata (JSON)
├── ip_address
├── user_agent
├── is_break_glass
└── timestamp
```

**Redis Usage:**
- TTL tracking for grants
- Rate limiting (future)
- Session caching (future)

### 5. Middleware

**Gateway Auth Middleware**
- Protects `/protected/*` endpoints
- JWT token extraction and validation
- Token revocation checking
- Audit logging for access attempts

**Metrics Middleware**
- Records HTTP request metrics
- Tracks response times (p50/p95/p99)
- Captures status codes and endpoints

### 6. Observability

**Prometheus Metrics:**
- `jit_access_requests_total` - Request counts by status
- `jit_approval_duration_seconds` - Approval latency
- `jit_active_grants_total` - Active grant count
- `jit_token_validations_total` - Token validation results
- `jit_http_request_duration_seconds` - API performance

**Grafana Dashboards:**
- System Overview
- API Performance
- Security Monitoring
- Audit Trail Visualization

**Alerts:**
- High approval latency (>5min)
- Denied request spikes
- Break-glass activations
- Token validation failures
- API SLO breaches (p95 > 120ms)

### 7. Notification System

**Slack Integration:**
- New request notifications → approvers
- Approval/denial → requesters
- Break-glass alerts → security team
- Token issuance confirmations

**Configurable:**
- Enable/disable via `SLACK_WEBHOOK_URL`
- Async, non-blocking
- Graceful degradation

## Data Flow

### Standard Access Request Flow

```
1. User submits request
   ↓
2. Policy evaluation (OPA)
   ├─ Check TTL limits
   ├─ Check time windows
   └─ Validate request format
   ↓
3. Request stored (pending)
   ↓
4. Slack notification → approvers
   ↓
5. Approver reviews & approves
   ↓
6. Policy evaluation (approval)
   ├─ Check approver role
   ├─ Verify not self-approval
   └─ Validate request state
   ↓
7. Request marked approved
   ↓
8. Slack notification → requester
   ↓
9. User issues token
   ↓
10. JWT generated & grant stored
    ↓
11. Token used at gateway
    ├─ JWT validation
    ├─ Revocation check
    └─ Audit logging
    ↓
12. Access to protected resource
```

### Break-Glass Flow

```
1. User submits break-glass request
   ↓
2. Policy evaluation (stricter)
   ├─ Max 30min TTL
   └─ Dual approval required
   ↓
3. First approver approves
   ↓
4. Request still pending (needs 2nd)
   ↓
5. Second approver approves
   ↓
6. Request approved
   ↓
7. Alert → security team
   ↓
8. Token issued with short TTL
   ↓
9. Enhanced audit logging
```

## Security Considerations

### Authentication
- API keys stored hashed
- JWT tokens signed and verified
- Token revocation support
- Session management via Redis

### Authorization
- Role-based access control
- Resource-level permissions
- Policy-as-code enforcement
- Self-approval prevention

### Audit Trail
- Immutable audit log
- Complete activity tracking
- IP address and user agent logging
- Break-glass event flagging
- CSV export for compliance

### Token Security
- Short-lived tokens (configurable TTL)
- Token hash storage (not plaintext)
- Revocation checking
- Scope-based access control

## Performance

### SLO Targets
- **API Latency**: p95 < 120ms
- **Approval Time**: median < 5 minutes
- **Token Validation**: p95 < 50ms
- **Availability**: 99.9% uptime

### Scalability
- Stateless API (horizontal scaling)
- Database connection pooling
- Redis caching layer
- OPA sidecar per instance

### Load Capacity
- Tested: 100 RPS token validation
- Tested: 10 RPS request submission
- Tested: 50 RPS concurrent approvals
- Database: PostgreSQL supports 1000s concurrent connections

## Deployment

### Docker Compose
- Single-command deployment
- All services pre-configured
- Volume persistence
- Health checks for all services

### Environment Variables
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis connection
- `OPA_URL` - Policy engine endpoint
- `JWT_SECRET_KEY` - Token signing key
- `SLACK_WEBHOOK_URL` - Notifications (optional)

### Dependencies
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- OPA latest
- Prometheus
- Grafana

## Future Enhancements

1. **Multi-region support**
   - Geographic distribution
   - Cross-region replication
   - Edge token validation

2. **Advanced policies**
   - ABAC (Attribute-Based Access Control)
   - Dynamic risk scoring
   - ML-based anomaly detection

3. **Integrations**
   - SSO/SAML
   - SCIM provisioning
   - Cloud provider IAM
   - PagerDuty/Opsgenie

4. **UI Improvements**
   - Full web UI (React/Next.js)
   - Mobile app
   - CLI tool
   - Browser extension

5. **Compliance**
   - SOC 2 audit logs
   - GDPR data retention
   - HIPAA compliance features
   - FedRAMP controls

