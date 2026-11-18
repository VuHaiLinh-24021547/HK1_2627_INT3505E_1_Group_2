---
name: api-data-and-query-optimization
description: >-
  Guides data modeling, field projections, GET pagination and caching, N+1 query
  prevention, and SQL injection prevention for the Match History API. Use when
  creating ORM models, implementing GET endpoints, optimizing database queries,
  or adding caching and pagination.
---

# API Data & Query Optimization

Use this skill when designing database models or implementing query/serialization logic for the LoL Match History API.

## Domain Entities & Endpoint Projections

Model the core entities cleanly (using normalized join tables rather than unindexed arrays where relational queries are needed):
- `player`: `id`, `name_with_hashtag`, recent games (up to 20).
- `game`: `id`, 10 players, 10 champions, `champion_level_in_the_end`, `objective_id`, `time_end`, `team_win` (`red` | `blue`).
- `champion`: `id`, `name`.
- `event_in_game`: `id`, `game_id`, `time_stamp`, `event_type` (`red kill` | `blue kill` | `red take objective` | `blue take objective`), plus future killer/victim/team fields.
- `item`: `id`, `name`.
- `objective`: `id`, `name`.

Enforce strict field projection per endpoint:
- `GET /players` -> return **only** `id`, `name_with_hashtag`.
- `GET /players/<int:id>` -> return all `player` fields (including `recent_games_id[20]`).
- `GET /games` -> return **only** `id`, `players_id`, `champion_id`, `team_win`, `time_end`.
- `GET /games/<int:id>` -> return all `game` fields **and** associated `event_in_game` records.
- `GET /champions`, `GET /items`, `GET /objectives` -> paginated list of `id`, `name`.
- `GET /players_games_info?player_id=&game_id=` -> filterable player-game detail endpoint.

## Mandatory GET Requirements

### 1. Pagination on Every Collection `GET`
- Accept `?page=1&per_page=20` (with a hard upper bound like `MAX_PER_PAGE = 100` to prevent abuse).
- Return pagination metadata alongside `data`:
  ```json
  {
    "data": [...],
    "meta": { "page": 1, "per_page": 20, "total": 120, "total_pages": 6 }
  }
  ```

### 2. Caching on Every `GET`
- Use Flask-Caching (`cache.cached` or manual cache keys) on all `GET` endpoints.
- **Include query parameters** (`page`, `per_page`, filters) in the cache key (`query_string=True`) so paginated/filtered responses do not collide.
- Invalidate relevant cache keys on `POST`/`PUT`/`PATCH`/`DELETE` mutations.

## Performance & Security Rules

### Avoid N+1 Queries
- Never access lazy-loaded relationships inside a loop over query results.
- Use eager loading (`selectinload` for one-to-many / many-to-many collections, `joinedload` for many-to-one) on queries like `/games`, `/games/<id>`, and `/players/<id>`.
- Verify query counts in tests using SQLAlchemy event listeners (`before_cursor_execute`) to assert constant query count regardless of page size.

### Avoid SQL Injection
- Always use SQLAlchemy ORM queries or bound parameters (`text("...").bindparams(...)`).
- **Never** interpolate user input (`request.args`, path params, JSON body) into SQL strings via f-strings, `%`, or `+`.
- Validate/whitelist sort columns and filter keys against an explicit allowlist.

## Verification Checklist
- [ ] All collection `GET` endpoints support `page` and `per_page` with capped max size and `meta` block.
- [ ] All `GET` endpoints cache responses keyed by path + query string.
- [ ] Eager loading is configured; query count for `N` items does not scale with `N`.
- [ ] Zero raw string-interpolated SQL exists in the codebase.

