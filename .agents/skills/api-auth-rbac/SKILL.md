---
name: api-auth-rbac
description: >-
  Guides implementing JWT and OAuth 2.0 authentication and role-based access
  control (RBAC), including restricting DELETE endpoints to the admin role.
  Use when adding auth endpoints, protecting routes, or configuring token/role
  validation.
---

# API Authentication & RBAC

Follow these security requirements for protecting the Match History API.

## Authentication: JWT + OAuth 2.0

1. **Token Standard (JWT)**:
   - Issue signed JWT access tokens containing standard claims (`sub`, `iat`, `exp`) and a `role` claim (e.g., `"user"` or `"admin"`).
   - Read tokens from the `Authorization: Bearer <token>` header.
   - Return `401 Unauthorized` (JSON) when the token is missing, malformed, expired, or has an invalid signature.
   - Load signing secrets/keys from environment/config (`SECRET_KEY` / `JWT_SECRET_KEY`), never hardcoded in production.

2. **OAuth 2.0 Support**:
   - Support OAuth 2.0 authorization flow (e.g., Authorization Code / Client Credentials or OAuth2 bearer token introspection/verification) and scope-based claims where applicable.
   - Map OAuth 2.0 user/client identity and scopes/roles cleanly into the request auth context (`g.current_user` / `get_jwt()`).

## Role-Based Access Control (RBAC)

- **Admin-Only `DELETE`**:
  - Every `DELETE` route across all blueprints **must** be decorated with a role guard requiring `role == "admin"` (e.g., `@roles_required("admin")`).
  - If the caller is unauthenticated -> `401 Unauthorized`.
  - If the caller is authenticated with a non-admin role (e.g., `"user"`) -> `403 Forbidden`.
  - Only `"admin"` may execute `DELETE` (returning `200` or `204`).

## Decorator Pattern

Keep auth/RBAC logic in a reusable decorator module (e.g., `app/auth/decorators.py`) so routes stay clean:
1. Verify JWT / OAuth2 bearer token.
2. Check required role(s) or scope(s).
3. Attach current user identity & role to request context.

## Verification Checklist
- [ ] Every `DELETE` endpoint rejects missing/invalid tokens with `401`.
- [ ] Every `DELETE` endpoint rejects non-admin tokens with `403`.
- [ ] Valid `admin` tokens succeed on `DELETE` and return `200`/`204`.
- [ ] No secrets or private keys are hardcoded in source files.

