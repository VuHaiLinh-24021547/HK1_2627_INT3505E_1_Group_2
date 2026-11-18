---
name: api-testing-and-postman
description: >-
  Guides writing per-function unit tests (pytest) and building an automated
  Postman/Newman test suite for the Match History API. Use when adding tests
  for new functions, verifying API requirements, or setting up Postman
  collections and automated test runs.
---

# API Testing & Postman Automation

Every function and endpoint in the Match History API must have automated test coverage.

## 1. Unit Tests (Per Function)

Use `pytest` with the Application Factory (`create_app("testing")`) and an isolated test database:

1. **Test Every Function**:
   - Every service/helper function, model method, auth decorator, and route handler must have dedicated unit tests.
   - Use fixtures in `tests/conftest.py` for `app`, `client`, `db_session`, `user_token`, and `admin_token`.
2. **Required Test Cases per Endpoint**:
   - **Happy path & JSON schema**: Status code, `Content-Type: application/json`, exact projected fields (e.g., `/players` only returns `id` and `name_with_hashtag`; `/games/<id>` includes `event_in_game`).
   - **Pagination**: `page`, `per_page`, `meta.total`, boundary/invalid page values.
   - **Caching**: Second identical `GET` hits cache (verify via spy/mock or DB query count = 0 on second call).
   - **N+1 Prevention**: Assert SQL query count stays bounded when fetching lists with multiple related records.
   - **SQL Injection**: Pass payloads like `' OR 1=1 --` in query/path params and assert safe handling (no 500 error, no leaked data).
   - **Auth & RBAC**: `DELETE` without token -> `401`; `DELETE` with `user` role -> `403`; `DELETE` with `admin` role -> `200`/`204`.

Run unit tests with:
```bash
pytest -v
```

## 2. Automated Postman Test Suite

Maintain a version-controlled Postman collection and environment in `postman/`:
- `postman/lol_match_history.postman_collection.json`
- `postman/local.postman_environment.json`

### Collection Structure
1. **Auth folder**: Obtain JWT/OAuth2 tokens for `user` and `admin` roles and store them in environment variables (`{{user_token}}`, `{{admin_token}}`).
2. **Resource folders** (`Players`, `Games`, `Champions`, `Items`, `Objectives`):
   - Test `GET` list (status `200`, JSON, pagination `meta`, response time/cache header).
   - Test `GET` by ID (projected fields, `404` for non-existent ID).
   - Test `DELETE` negative cases (`401` without auth, `403` with `{{user_token}}`) and positive case (`200`/`204` with `{{admin_token}}`).

### Automated Execution (Newman)
Run the full Postman suite from CLI:
```bash
newman run postman/lol_match_history.postman_collection.json -e postman/local.postman_environment.json
```

## Verification Checklist
- [ ] `pytest` passes with unit tests covering every function.
- [ ] Cache hit, pagination, N+1 query count, SQLi payload, and RBAC `401`/`403` are all tested.
- [ ] Postman collection + environment files exist in `postman/` and pass under `newman run`.

