---
name: flask-api-architecture
description: >-
  Guides designing and structuring the Flask REST API using the Application Factory
  pattern, Blueprints, Extensions, consistent JSON responses, and safe/idempotent
  HTTP method semantics. Use when scaffolding the project, adding new endpoints or
  blueprints, or reviewing RESTful API structure.
---

# Flask API Architecture

Follow this structure and these RESTful conventions when building or extending the League of Legends Match History API.

## Project Layout (Application Factory + Blueprints + Extensions)

Organize the application into modular packages rather than a single `app.py`:

```text
app/
├── __init__.py          # create_app(config_name) Application Factory
├── config.py            # Development, Testing, Production configs
├── extensions.py        # Unbound extension instances (db, cache, jwt, migrate, etc.)
├── models/              # SQLAlchemy models (player, game, champion, event_in_game, item, objective)
├── schemas/             # Serialization / validation schemas (field projections)
├── blueprints/          # Feature blueprints: players, games, champions, items, objectives, auth
│   └── __init__.py      # Register blueprints on the app in create_app()
└── errors.py            # Global JSON error handlers (400, 401, 403, 404, 409, 422, 500)
```

### Rules
1. **Extensions (`extensions.py`)**: Instantiate extensions without binding to an app (`db = SQLAlchemy()`, `cache = Cache()`, etc.), then call `ext.init_app(app)` inside `create_app()`. Never import `app` at module level.
2. **Blueprints**: Group routes by resource (`/players`, `/games`, `/champions`, `/items`, `/objectives`, `/auth`). Register all blueprints in `create_app()`.
3. **JSON-Only Responses**: Every endpoint and every error handler (`4xx`/`5xx`) must return `application/json` with a consistent envelope (e.g., `{"data": ..., "meta": ...}` for success, `{"error": {"code": ..., "message": ...}}` for errors). Never return HTML error pages.

## RESTful & HTTP Method Semantics

Ensure all endpoints respect HTTP safety and idempotency:
- **`GET` / `HEAD` / `OPTIONS`**: Must be **safe** and **idempotent** (read-only, no state mutation or side effects).
- **`PUT`**: Must be **idempotent** (replacing a resource at `/<resource>/<id>` produces the same state if called multiple times).
- **`DELETE`**: Must be **idempotent** (deleting `/<resource>/<id>` leaves the resource absent on repeated calls; restricted to `admin` role).
- **`POST`**: Used for non-idempotent creation (e.g., `/games`, `/players`). Return `201 Created` with `Location` header where appropriate.

## Verification Checklist
- [ ] `create_app("testing")` creates an isolated app instance without circular imports.
- [ ] All routes live inside Blueprints, not on a global `app` object.
- [ ] All extensions are initialized via `init_app(app)` in `create_app()`.
- [ ] Every endpoint and HTTP error returns valid JSON with proper status codes (`200`, `201`, `204`, `400`, `401`, `403`, `404`).
- [ ] `GET` handlers perform zero database writes.

