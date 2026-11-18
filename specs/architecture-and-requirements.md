# Architecture, Security & Testing Specification

## 1. Flask Application Structure

Use the **Application Factory**, **Extensions**, and **Blueprints** pattern:

```text
app/
├── __init__.py          # create_app(config_name="default")
├── config.py            # DevConfig, TestConfig, ProdConfig
├── extensions.py        # db, cache, jwt, migrate (unbound)
├── errors.py            # JSON handlers for 400, 401, 403, 404, 422, 500
├── auth/
│   ├── decorators.py    # @jwt_or_oauth_required, @roles_required("admin")
│   └── routes.py        # /auth/login, /auth/oauth/token
├── models/              # SQLAlchemy ORM models
├── schemas/             # Marshmallow / Pydantic / serializer projections
└── blueprints/
    ├── players.py       # /api/v1/players
    ├── games.py         # /api/v1/games
    ├── champions.py     # /api/v1/champions
    ├── items.py         # /api/v1/items
    ├── objectives.py    # /api/v1/objectives
    └── docs.py          # /openapi.json and Swagger UI at /docs
```

## 2. HTTP Method Semantics (Safe & Idempotent)

| Method | Safe | Idempotent | Auth / Role | Behavior |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | Yes | Yes | Authenticated (`user` / `admin`) | Read-only, paginated, cached by path + query string |
| `POST` | No | No | Authenticated (`user` / `admin`) | Create resource (`201 Created`), invalidates list cache |
| `PUT` | No | Yes | Authenticated (`user` / `admin`) | Full replacement (`200 OK`), invalidates item + list cache |
| `DELETE` | No | Yes | **`admin` role only** | Delete resource (`204 No Content`), invalidates item + list cache |

## 3. Caching & Pagination Contract

- **Pagination**: Every collection `GET` accepts `?page=1&per_page=20` (`1 <= per_page <= 100`) and returns:
  ```json
  {
    "data": [...],
    "meta": { "page": 1, "per_page": 20, "total": 0, "total_pages": 0 }
  }
  ```
- **Caching**: Every `GET` endpoint caches responses using Flask-Caching (`query_string=True` so `?page=1` and `?page=2` never collide) and sets `Cache-Control` / `ETag` headers. Mutations (`POST`, `PUT`, `DELETE`) invalidate affected resource caches.

## 4. Security & RBAC Matrix

- **Authentication**: Accepts `Authorization: Bearer <token>` issued via JWT (`/auth/login`) or OAuth 2.0 (`/auth/oauth/token`).
- **RBAC**:
  - Missing / invalid / expired token -> `401 Unauthorized` (JSON).
  - Non-`admin` token calling any `DELETE` endpoint -> `403 Forbidden` (JSON).
  - `admin` token calling `DELETE` -> `204 No Content`.
- **SQL Injection Prevention**: Only SQLAlchemy ORM / bound parameters; zero raw string interpolation.

## 5. Verification & Testing Matrix

| Layer | Tool | Required Coverage |
| :--- | :--- | :--- |
| **Unit Tests** | `pytest` | 100% of functions (models, serializers, auth decorators, blueprint handlers) |
| **Query & Cache** | `pytest` + SQLAlchemy event hook | Assert constant query count (no N+1) and 0 DB queries on cache hit |
| **Security** | `pytest` | SQLi payloads return `400`/`404` (never `500`), `DELETE` `401`/`403`/`204` |
| **API E2E Suite** | Postman + `newman run` | Automated collection testing all endpoints, pagination, cache, JWT/OAuth2, RBAC |

