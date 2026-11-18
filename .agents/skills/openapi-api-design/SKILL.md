---
name: openapi-api-design
description: >-
  Guides designing and maintaining the OpenAPI 3.0 specification and Swagger UI
  documentation for the League of Legends Match History API. Use when defining
  new endpoints, request/response schemas, security schemes, or syncing API
  docs with Flask blueprints.
---

# OpenAPI Spec Design

Keep an accurate OpenAPI 3.0 specification (e.g., `openapi.yaml`) as the contract for the Match History API, served via Swagger UI (`/docs`).

## Spec Structure

1. **`info` & `servers`**: Title, version, and local/staging server URLs.
2. **`components.securitySchemes`**:
   - `BearerAuth` (`type: http`, `scheme: bearer`, `bearerFormat: JWT`)
   - `OAuth2` (`type: oauth2`, appropriate flow & scopes)
3. **`components.schemas`**:
   - Separate summary vs. detail schemas where projections differ:
     - `PlayerSummary` (`id`, `name_with_hashtag`) vs. `PlayerDetail` (all fields + `recent_games_id`).
     - `GameSummary` (`id`, `players_id`, `champion_id`, `team_win`, `time_end`) vs. `GameDetail` (all `game` fields + `events: EventInGame[]`).
     - `Champion`, `Item`, `Objective`, `EventInGame`, `PaginationMeta`, `ErrorResponse`.
   - Use `enum` for categorical fields:
     - `team_win`: `[red, blue]`
     - `event_type`: `[red kill, blue kill, red take objective, blue take objective]`
4. **`paths`**:
   - Document `page` and `per_page` query parameters on all collection `GET` endpoints.
   - Document `401` and `403` responses and `security` requirements on protected/`DELETE` endpoints.

## Sync & Validation
- Serve the spec at `/openapi.json` and Swagger UI at `/docs` via a dedicated docs blueprint.
- Validate the OpenAPI YAML whenever endpoints or schemas change so the spec never drifts from Flask routes.

## Verification Checklist
- [ ] `openapi.yaml` defines all endpoints, query params, enums, and projected schemas.
- [ ] `BearerAuth` and `OAuth2` security schemes are declared and attached to protected routes.
- [ ] Swagger UI loads cleanly at `/docs` without schema validation errors.

