---
name: rest-api-design
description: Designs, implements, reviews, and load-tests production-grade RESTful APIs. Enforces strict REST principles, JWT/OAuth 2.0 auth, meaningful HTTP status codes, idempotency, data-rich payloads, safe filtering, cursor-based pagination, RFC 9457 global exception handling, strict versioning, automated API testing, and Locust load testing. Use whenever designing endpoints, writing backend APIs, reviewing API contracts, or generating API tests.
---

# Production REST API Design & Engineering Skill

## Goal
Ensure every API designed, generated, or modified is secure, predictable, resilient, backward-compatible, and thoroughly verified under both functional and load conditions.

## Execution Workflow
When the user requests a new API, endpoint, or refactor, follow this sequence:
1. **Contract First**: Define the resource URI, HTTP method, version, request/response schemas, auth scopes, and error cases before writing handler code.
2. **Implement Core Standards**: Apply all mandatory rules below (REST, Auth, Idempotency, Filtering, Cursor Pagination, Global Exception Handler).
3. **Verify with Automated Tests**: Write unit, integration, and security/edge-case tests.
4. **Verify Performance with Locust**: Generate or update `locustfile.py` with realistic user flows and SLO assertions.
5. **Run Final Audit**: Check every deliverable against the Verification Checklist before finishing.

---

## 1. Strict REST Compliance
- **Resource-Oriented URIs**: Use lowercase, kebab-case, **plural nouns** for collections (e.g., `/api/v1/orders`, `/api/v1/orders/{orderId}/items`).
- **No Verbs in Paths**: Express actions strictly through HTTP methods (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`).
- **Statelessness**: Never rely on server-side session state; every request must carry all context required to authenticate and process it.
- **Content Negotiation**: Require `Content-Type: application/json` for requests with bodies and return `application/json` (or `application/problem+json` for errors).

## 2. Strict API Versioning
- **Explicit Major Version**: Prefix all endpoints with a major version in the URI path: `/api/v1/...`. Never expose unversioned business endpoints.
- **Backward Compatibility Policy**:
  - *Non-breaking (allowed in same version)*: Adding optional request fields, adding new response fields, adding new endpoints.
  - *Breaking (MUST bump major version, e.g., `v2`)*: Removing/renaming fields, changing field types or semantics, tightening validation on existing fields, changing status codes or auth requirements.
- **Deprecation Lifecycle**: Deprecated versions/endpoints MUST include `Deprecation`, `Sunset` (RFC 8594), and `Link: <migration-guide>; rel="sunset"` headers.

## 3. Authentication & Authorization (OAuth 2.0 + JWT)
- **Authentication (OAuth 2.0)**:
  - Use **Authorization Code Flow with PKCE** for user-facing apps and **Client Credentials Flow** for machine-to-machine (M2M) services.
  - Accept bearer tokens exclusively via the `Authorization: Bearer <token>` header. Never accept tokens in query strings.
- **JWT Validation**:
  - Verify cryptographic signature using an explicit asymmetric algorithm allowlist (`RS256` or `ES256`); explicitly reject `alg: none`.
  - Validate standard claims on every request: `exp`, `nbf`, `iss`, `aud`, and `sub`.
  - Enforce short-lived access tokens (5–15 minutes) paired with refresh token rotation and revocation support.
- **Authorization**:
  - Enforce **RBAC/ABAC and OAuth 2.0 scopes** (e.g., `orders:read`, `orders:write`) on every protected endpoint.
  - Enforce **object-level authorization** (verify resource ownership/tenant isolation) on every resource fetch or mutation to prevent BOLA/IDOR.
  - Never trust client-supplied `user_id`, `tenant_id`, or `role` fields from request bodies or headers; derive identity strictly from the verified JWT claims.

## 4. Meaningful HTTP Status Codes
Never return `200 OK` with an embedded error object. Use exact HTTP semantics:
- `200 OK`: Successful `GET`, `PUT`, `PATCH`, or synchronous action returning a body.
- `201 Created`: Resource successfully created (`POST`). MUST include a `Location` header pointing to the new resource URI and return the created resource in the body.
- `202 Accepted`: Asynchronous job accepted for background processing (return job status URI/ID).
- `204 No Content`: Successful `DELETE` or update returning no response body.
- `400 Bad Request`: Malformed JSON, invalid query syntax, or unsupported filter/sort parameters.
- `401 Unauthorized`: Missing, malformed, expired, or invalid credentials/JWT (include `WWW-Authenticate` header).
- `403 Forbidden`: Authenticated caller lacks required scope, role, or object-level permission.
- `404 Not Found`: Resource does not exist (or intentionally masked for unauthorized access).
- `409 Conflict`: Resource state conflict, duplicate unique key, or in-flight idempotency lock collision.
- `422 Unprocessable Entity`: Syntactically valid payload that fails domain/schema validation rules.
- `429 Too Many Requests`: Rate limit exceeded (include `Retry-After` header).
- `500 Internal Server Error` / `503 Service Unavailable`: Unhandled server failures or downstream outages.

## 5. Data-Carrying Request & Response Bodies
- **Rich, Explicit Payloads**: Every `200`/`201` response MUST return meaningful resource data (never vague messages like `{"status": "ok"}` or `{"success": true}`).
- **Consistent Casing & Schemas**: Enforce one naming convention across the entire API (default: `snake_case` or `camelCase` consistently) and validate all request bodies against strict DTOs/schemas (reject or strip unknown fields).
- **Standardized Envelopes**:
  - Single resource: return the resource object directly (or `{ "data": { ... } }` consistently across the API).
  - Collections:
    ```json
    {
      "data": [ { "id": "ord_123", "status": "paid", "created_at": "2026-11-21T09:00:00Z" } ],
      "pagination": {
        "limit": 20,
        "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNi0xMS0yMVQwOTowMDowMFoiLCJpZCI6Im9yZF8xMjMifQ==",
        "has_more": true
      }
    }
    ```
- **Data Minimization**: Never expose internal database secrets, password hashes, raw tokens, or internal stack details in response bodies.

## 6. Idempotency
- **Native Idempotency**: `GET`, `HEAD`, `PUT`, and `DELETE` MUST be naturally idempotent.
- **Explicit Idempotency Key for Mutations**: All non-idempotent write endpoints (`POST`, and non-idempotent `PATCH`)—especially financial, order, or state-changing operations—MUST support (and for critical mutations, require) the `Idempotency-Key: <uuid-v4>` header.
- **Server-Side Handling Rules**:
  1. Store `(idempotency_key, caller_scope, request_hash, response_status, response_body)` in an atomic store (e.g., Redis/PostgreSQL) with a defined TTL (e.g., 24 hours).
  2. If the key is currently being processed by another concurrent request, return `409 Conflict`.
  3. If the key exists with a **matching** `request_hash`, replay the exact original status code and response body without re-executing side effects.
  4. If the key exists with a **different** `request_hash`, reject with `422 Unprocessable Entity` (or `409 Conflict`) to prevent accidental key reuse.

## 7. Safe Filtering & Sorting
- **Explicit Allowlists**: Define strict allowlists for filterable and sortable fields per endpoint. Reject unknown fields or operators with `400 Bad Request`—never dynamically interpolate query keys into SQL/NoSQL queries.
- **Standardized Syntax**:
  - Exact/multi-value filtering: `?status=paid&currency=USD,EUR`
  - Range/comparison operators: `?created_at[gte]=2026-01-01T00:00:00Z&amount[lte]=5000`
  - Deterministic sorting: `?sort=-created_at,id` (`-` prefix for descending).
- **Index Alignment**: Ensure every allowed filter/sort combination is backed by an appropriate database index.

## 8. Cursor-Based Pagination
- **Mandatory for Collections**: All list endpoints MUST use cursor-based (keyset) pagination. Do NOT use `OFFSET`/`LIMIT` pagination for scalable or mutable datasets.
- **Parameters**:
  - `limit`: Integer with a safe default (e.g., `20`) and a strict upper bound (e.g., max `100`). Reject values `<= 0` or `> max` with `400 Bad Request`.
  - `cursor`: Opaque, URL-safe Base64-encoded JSON token containing deterministic tie-breaker sort keys (e.g., `{"created_at": "...", "id": "..."}`).
- **Query Mechanics**: Fetch `limit + 1` records using keyset comparison (`(created_at, id) < (:cursor_created_at, :cursor_id)`). If `limit + 1` rows exist, set `has_more = true`, trim the extra row, and encode the last returned item's sort keys into `next_cursor`. Return `400 Bad Request` if `cursor` is corrupted or tampered with.

## 9. Centralized Global Exception Handler
Every API MUST register a single global exception/error middleware that catches all domain, validation, auth, and unhandled exceptions and serializes them according to **RFC 9457 (Problem Details for HTTP APIs)** with `Content-Type: application/problem+json`:

```json
{
  "type": "https://api.example.com/errors/validation-failed",
  "title": "Unprocessable Entity",
  "status": 422,
  "detail": "One or more request fields failed validation.",
  "instance": "/api/v1/orders",
  "trace_id": "9f86d081884c7d659a2feaa0c55ad015",
  "errors": [
    {
      "field": "items[0].quantity",
      "code": "min_value",
      "message": "Quantity must be greater than or equal to 1."
    }
  ]
}
```
- **Security Rule**: Log full stack traces and internal error details server-side keyed by `trace_id`, but NEVER expose stack traces, SQL statements, or framework internals in API responses.

## 10. Automated Testing Requirements
Every API implementation MUST include automated tests covering:
- **Contract & Schema Validation**: Response payloads match OpenAPI/DTO definitions and headers (`Content-Type`, `Location`, versioning/deprecation headers).
- **Happy Paths**: Full CRUD lifecycle, filtering, sorting, and multi-page cursor pagination traversal (including empty results and last page `has_more: false`).
- **Security & Auth**: Missing token (`401`), expired/tampered JWT (`401`), insufficient scope (`403`), and cross-user/cross-tenant BOLA attempts (`403`/`404`).
- **Idempotency**: Duplicate `Idempotency-Key` with identical payload replays response without creating duplicate records; same key with modified payload fails with `422`/`409`.
- **Exception Handler**: Malformed JSON (`400`), validation failures (`422` with field-level `errors`), and simulated unhandled failures (`500` RFC 9457 payload with no stack trace leak).

## 11. Load Testing with Locust
Every production API MUST include a runnable Locust test suite (`tests/load/locustfile.py`) that validates performance under concurrency:
- **Realistic Behavior**: Use `HttpUser` with realistic `wait_time = between(0.5, 2.0)` and weighted `@task` ratios mirroring production read/write mixes (e.g., 80% reads, 20% writes).
- **Auth Lifecycle**: Acquire or refresh OAuth 2.0 / JWT tokens in `on_start` and attach `Authorization: Bearer <token>` headers.
- **Data & Idempotency**: Generate unique test data and UUIDv4 `Idempotency-Key` headers per write task, plus dedicated tasks that intentionally test idempotency replay and cursor pagination traversal.
- **Strict Response Validation**: Use `with self.client.get(..., catch_response=True) as res:` to validate HTTP status codes, JSON structure, and latency budgets.
- **Execution & SLOs**: Document and run a headless command with clear pass/fail criteria (e.g., error rate `< 1%`, p95 latency `< 300ms`, p99 `< 800ms`):
  ```bash
  locust -f tests/load/locustfile.py --headless \
    -u 100 -r 10 -t 2m \
    --host https://staging.api.example.com \
    --csv=reports/load_test
  ```

---

## Constraints (MUST NOT)
- Do NOT expose unversioned API routes.
- Do NOT use `OFFSET`/`LIMIT` pagination on list endpoints.
- Do NOT return `200 OK` for error conditions.
- Do NOT bypass object-level authorization or trust client-supplied identity/role fields.
- Do NOT accept unvalidated filter/sort fields directly into database queries.
- Do NOT leak stack traces, internal IPs, or database error strings in responses.
- Do NOT ship an API without automated negative/security tests and a runnable `locustfile.py`.

## Final Verification Checklist
Before completing any API task, verify and report:
- [ ] Endpoints use `/api/v{N}/` versioning and plural RESTful resource nouns.
- [ ] OAuth 2.0 + JWT verification (`alg`, `exp`, `iss`, `aud`) and object-level RBAC/scopes are enforced.
- [ ] All responses use meaningful HTTP status codes and data-carrying JSON bodies.
- [ ] Non-idempotent write endpoints enforce `Idempotency-Key` with payload hash validation.
- [ ] List endpoints enforce allowlisted filtering/sorting and opaque cursor-based pagination.
- [ ] Global exception handler returns RFC 9457 `application/problem+json` with `trace_id` and zero stack trace leaks.
- [ ] Automated unit/integration/security tests pass.
- [ ] `locustfile.py` is implemented and verified against defined latency and error-rate SLOs.