# Just-In-Time Access & Policy Gateway (JIT-Access)

A small service that lets engineers request **time-boxed access** to resources (e.g., “prod-read on orders DB for 2 hours”), routes **approvals**, enforces **policy-as-code**, issues **short-lived tokens**, and keeps **audit-ready logs & metrics**.

---

## TL;DR (What to Build in ~1 Month)
- **API service** (FastAPI/Flask) + **Postgres** + **Redis** + **OPA/Oso** policy engine
- **Approvals & grants**: request → approve/deny → short-lived token → enforce in a demo gateway
- **Observability**: Prometheus metrics + Grafana dashboards + alerts
- **Load tests**: k6; target **p95 < 120ms** for core endpoints at moderate RPS
- **Security**: RBAC roles, TTL grants, break-glass flow, complete audit trail
- **Polish**: Docker Compose one-command bring-up, seed data, readme, demo script

---

## Why This Fits the Resume
- Mirrors **RBAC, approvals, policy checks, dashboards, runbooks** (JPMC + risk platform)
- Strong **Backend/Platform + Security/Observability** signal
- Clear demo value (UI/Slack approval + live dashboard)

---

## Scope & Non-Goals
**In-scope**
- Token-based access to sample resources (HTTP gateway + DB proxy example)
- Policy-as-code (max TTLs, who can approve, time windows, justification)
- Audit, metrics, load testing, runbooks

**Out-of-scope**
- Real SSO/SCIM, enterprise IAM integration, production-grade PKI/HSM
- Multi-region HA; advanced data masking/ABAC (can stub)

---

## Stack (Suggested)
- **API:** FastAPI (or Flask) + Pydantic
- **Policy:** OPA (Rego) or Oso
- **DB:** Postgres (state + audit)
- **Cache/Queues:** Redis (TTL, idempotency, simple rate-limits)
- **AuthZ token:** JWT (PyJWT) with JWKs endpoint
- **Obs:** Prometheus client + Grafana
- **Load:** k6
- **Packaging:** Docker Compose
- **UI (optional):** Minimal Next.js/React or Slack slash command

---

## Milestones (Four Weeks)

### Week 1 — Core Flows
- Users/roles (requester, approver, admin); GitHub OAuth stub if desired
- Models: `User, Resource, Policy, AccessRequest, Grant, AuditEvent`
- Happy path: submit request → approve/deny → issue short-lived token
- Minimal UI (or Swagger + cURL) for submit/list/approve

### Week 2 — Policy & Enforcement
- Policy-as-code with OPA/Oso (max TTLs, approver rules, change windows)
- **Gateway middleware** to validate JWT scope & TTL for a sample API
- **DB proxy** demo: readonly role access with token bound to scope
- **Break-glass** path: dual approval + shorter TTL + special audit flag

### Week 3 — Observability & Ops
- Metrics: request rate, approval latency, grant count, token failures, p50/p95
- Dashboards & alerts: approval latency SLO, stale grants, deny spikes
- k6 load scenarios; document p95/p99 results
- Runbooks (markdown) for common issues

### Week 4 — Hardening & Polish
- Append-only audit, CSV export
- Slack `/access` (or email) notifier
- Seed data, one-command `docker compose up`
- README, demo script, screenshots

---

## High-Level Architecture

```text
+-------------------+       +--------------------+       +------------------+
|  UI / Slack Cmd   | <---> |   JIT-Access API   | <---> |   Postgres (RDS) |
+-------------------+       | (FastAPI/Flask)    |       +------------------+
                            |  - JWT Issue       |               ^
                            |  - Approvals       |               |
                            |  - Audit Log       |               |
                            +---------^----------+               |
                                      |                          |
                           +----------+-----------+      +-------+-------+
                           |     Policy Engine    |      |     Redis     |
                           | (OPA sidecar/Oso)    |      | TTL, idemp.   |
                           +----------^-----------+      +---------------+
                                      |
                              +-------+---------+
                              |  Demo Gateway   |  <-- protects sample API/DB
                              |  (middleware)   |
                              +-----------------+
