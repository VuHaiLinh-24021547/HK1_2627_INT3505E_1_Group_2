# Đặc Tả Yêu Cầu Kỹ Thuật: Backend Web Lịch Sử Đấu LMHT (Phong Cách Coachless)

> Tài liệu này được biên soạn theo cấu trúc **Spec-Driven Development** dành cho AI coding agent (Antigravity) triển khai trọn gói backend **Python / Flask**, cơ sở dữ liệu **PostgreSQL + Redis**, kiểm thử hàm bằng **pytest**, và kiểm thử API endpoint tự động bằng **Postman + Newman**.

---

## 1. Mục tiêu sản phẩm và phạm vi kiến trúc

Xây dựng hệ thống backend cho trang web tra cứu và phân tích lịch sử đấu Liên Minh Huyền Thoại tương tự [Coachless Review](https://coachless.gg/review), cho phép người dùng:

1. Tra cứu hồ sơ người chơi theo Riot ID (`gameName#tagLine`) và khu vực máy chủ (ưu tiên `vn2`, hỗ trợ `kr`, `euw1`, `na1`).
2. Đồng bộ bất đồng bộ danh sách trận đấu gần nhất từ [Riot Games API](https://developer.riotgames.com/apis) vào cơ sở dữ liệu mà không bị dính lỗi giới hạn tốc độ (`HTTP 429`).
3. Xem danh sách lịch sử đấu phân trang có bộ lọc theo tướng và chế độ chơi, hiển thị đầy đủ thông tin tướng, trang bị, ngọc bổ trợ, phép bổ trợ từ [Data Dragon](https://developer.riotgames.com/docs/lol).
4. Mở chi tiết hậu trận của 10 người chơi kèm dữ liệu diễn biến từng phút (`timeline`: chênh lệch vàng, chênh lệch XP, mốc sự kiện lớn, lịch sử mua đồ) để vẽ biểu đồ phân tích trên giao diện.

### Ngăn xếp công nghệ bắt buộc

| Thành phần | Công nghệ / Thư viện | Vai trò |
| :--- | :--- | :--- |
| Ngôn ngữ & Web Framework | Python 3.11+, Flask 3.x (Application Factory + Blueprints) | Xây dựng REST API JSON |
| ORM & Migration | SQLAlchemy 2.0, Flask-SQLAlchemy, Flask-Migrate (Alembic) | Quản lý lược đồ và truy vấn PostgreSQL |
| Cơ sở dữ liệu chính | PostgreSQL 15+ (hỗ trợ `JSONB` và B-Tree Index) | Lưu hồ sơ, trận đấu, người tham gia, timeline, tài nguyên tĩnh |
| Bộ đệm & Hàng đợi | Redis 7+, RQ (Redis Queue) hoặc Celery | Cache hồ sơ/tài nguyên, chạy job đồng bộ trận đấu và kiểm soát Rate Limit |
| Validation & HTTP Client | Pydantic v2 (hoặc Marshmallow), `httpx` / `requests` | Kiểm tra payload và gọi Riot API / Data Dragon |
| Kiểm thử đơn vị & tích hợp | `pytest`, `pytest-cov`, `responses` (hoặc `respx`) | Kiểm thử logic nghiệp vụ, parser, rate limiter và Flask routes |
| Kiểm thử API End-to-End | Postman Collection v2.1 + Newman CLI (`newman`) | Kiểm thử hợp đồng REST API tự động qua script |

---

## 2. Cấu trúc thư mục dự án mục tiêu

Antigravity cần khởi tạo đúng cấu trúc thư mục sau để tách biệt rõ tầng routing, dịch vụ gọi Riot API, model dữ liệu và bộ kiểm thử:

```text
lol-match-history/
├── app/
│   ├── __init__.py                 # create_app(config_name), đăng ký Blueprints & extensions
│   ├── config.py                   # DevConfig, TestConfig, ProdConfig (đọc từ .env)
│   ├── extensions.py               # db (SQLAlchemy), migrate, redis_client, rq_queue
│   ├── models/
│   │   ├── __init__.py
│   │   ├── player.py               # Bảng players
│   │   ├── match.py                # Bảng matches, match_participants, match_timelines
│   │   └── static_asset.py         # Bảng static_assets
│   ├── services/
│   │   ├── riot_client.py          # HTTP client gọi Riot API + Token Bucket + xử lý 429
│   │   ├── routing.py              # Ánh xạ platform (vn2) -> account host (asia) & match host (sea)
│   │   ├── ddragon_service.py      # Đồng bộ versions.json, champion, item, runes, spells
│   │   ├── sync_service.py         # Luồng đồng bộ hồ sơ + 20 trận mới (có deduplication)
│   │   └── review_service.py       # Tổng hợp bảng điểm 10 người + timeline Gold/XP Diff
│   ├── api/
│   │   ├── __init__.py
│   │   ├── errors.py               # Error handlers chuẩn JSON (400, 404, 429, 502)
│   │   ├── health.py               # GET /api/v1/health
│   │   ├── players.py              # GET profile, POST sync, GET matches
│   │   ├── matches.py              # GET match review + lazy-fetch timeline
│   │   └── static_data.py          # GET static catalog theo patch
│   └── workers/
│       └── sync_worker.py          # Background worker xử lý job đồng bộ Riot API
├── migrations/                     # Alembic migrations
├── tests/
│   ├── conftest.py                 # App fixture, test DB, mock Redis, sample Riot JSON
│   ├── fixtures/                   # File JSON mẫu từ Account-V1, Match-V5, Timeline, DDragon
│   ├── unit/
│   │   ├── test_routing.py
│   │   ├── test_riot_client.py
│   │   ├── test_ddragon_service.py
│   │   └── test_review_service.py
│   └── integration/
│       ├── test_players_api.py
│       ├── test_matches_api.py
│       └── test_static_api.py
├── postman/
│   ├── lol-match-history.postman_collection.json
│   └── local.postman_environment.json
├── scripts/
│   └── run_newman.sh               # Script chạy Newman kiểm thử toàn bộ API endpoint
├── docker-compose.yml              # PostgreSQL + Redis cho môi trường local/test
├── .env.example                    # RIOT_API_KEY, DATABASE_URL, REDIS_URL, SYNC_COOLDOWN_SEC
├── requirements.txt
└── pytest.ini
```

---

## 3. Tích hợp Riot Games API và Data Dragon

### 3.1. Quy tắc định tuyến (Platform vs. Regional Routing)

Theo tài liệu [Riot Developer Portal — League of Legends](https://developer.riotgames.com/docs/lol), [Riot Developer Relations](https://support-developer.riotgames.com/hc/en-us/articles/22698698001939-League-of-Legends) và hướng dẫn định tuyến [DarkIntaqt Routing Guide](https://darkintaqt.com/blog/routing), `app/services/routing.py` phải cài đặt chính xác bảng ánh xạ 3 loại host:

| Mã khu vực (User Input) | Platform Host (`summoner-v4`, `league-v4`) | Account Host (`account-v1`) | Match Host (`match-v5`) |
| :--- | :--- | :--- | :--- |
| `vn2` (Việt Nam) | `vn2.api.riotgames.com` | `asia.api.riotgames.com` | `sea.api.riotgames.com` |
| `sg2` / `tw2` / `oc1` | `{region}.api.riotgames.com` | `asia.api.riotgames.com` | `sea.api.riotgames.com` |
| `kr` / `jp1` | `{region}.api.riotgames.com` | `asia.api.riotgames.com` | `asia.api.riotgames.com` |
| `euw1` / `eun1` / `tr1` / `ru` | `{region}.api.riotgames.com` | `europe.api.riotgames.com` | `europe.api.riotgames.com` |
| `na1` / `br1` / `la1` / `la2` | `{region}.api.riotgames.com` | `americas.api.riotgames.com` | `americas.api.riotgames.com` |

> **Lưu ý quan trọng:** `account-v1` không có cụm `sea`, nên khu vực `vn2` bắt buộc định tuyến `account-v1` sang `asia.api.riotgames.com`, còn `match-v5` sang `sea.api.riotgames.com`.

### 3.2. Danh sách Endpoint Riot API & Data Dragon cần gọi

| Nguồn | Endpoint | Mục đích sử dụng |
| :--- | :--- | :--- |
| [Account-V1](https://developer.riotgames.com/apis) | `GET /riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}` | Chuyển Riot ID sang `puuid` bất biến |
| [Summoner-V4](https://jentic.com/apis/developer.riotgames.com/riot-games) | `GET /lol/summoner/v4/summoners/by-puuid/{encryptedPUUID}` | Lấy `profileIconId`, `summonerLevel` |
| [League-V4](https://github.com/Izakun/n8n-nodes-leagueoflegends) | `GET /lol/league/v4/entries/by-puuid/{encryptedPUUID}` | Lấy hạng Đơn/Đôi (`RANKED_SOLO_5x5`): `tier`, `rank`, `leaguePoints`, `wins`, `losses` |
| [Match-V5 IDs](https://developer.riotgames.com/apis) | `GET /lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=20` | Lấy danh sách mã trận mới nhất (hỗ trợ tham số `queue`) |
| [Match-V5 Detail](https://developer.riotgames.com/apis) | `GET /lol/match/v5/matches/{matchId}` | Lấy thông tin chi tiết 10 người chơi (chỉ gọi nếu `matchId` chưa tồn tại trong DB) |
| [Match-V5 Timeline](https://github.com/Izakun/n8n-nodes-leagueoflegends) | `GET /lol/match/v5/matches/{matchId}/timeline` | Gọi lười (lazy-fetch) khi người dùng mở trang chi tiết trận đấu lần đầu |
| [Data Dragon](https://riot-api-libraries.readthedocs.io/en/latest/ddragon.html) | `GET https://ddragon.leagueoflegends.com/api/versions.json` | Kiểm tra bản vá mới nhất (phần tử đầu mảng) |
| [Data Dragon Static](https://developer.riotgames.com/docs/lol) | `GET https://ddragon.leagueoflegends.com/cdn/{ver}/data/{lang}/{file}.json` | Tải `champion.json`, `item.json`, `runesReforged.json`, `summoner.json` (`vi_VN` & `en_US`) |

### 3.3. Bảo mật API Key & kiểm soát Rate Limit

Theo [Riot Developer Portal — Rate Limiting](https://developer.riotgames.com/docs/portal):

- **Bảo mật:** Truyền `X-Riot-Token` trong HTTP header ở backend, đọc từ biến môi trường `RIOT_API_KEY`. Tuyệt đối không trả key ra response hay log.
- **Hạn mức Development / Personal Key:** `20 requests / 1 giây` và `100 requests / 2 phút` trên mỗi khu vực. (Production Key khởi điểm: `500 requests / 10 giây` và `30.000 requests / 10 phút`.)
- **Xử lý lỗi `429`:** `RiotClient` phải đọc header `Retry-After`, tạm dừng theo thời gian yêu cầu (có giới hạn số lần retry tối đa, mặc định 2 lần) và tuyệt đối không spam request liên tiếp.
- **Cơ chế chống trùng lặp (Deduplication):** Trước khi gọi `GET /matches/{matchId}`, truy vấn `SELECT match_id FROM matches WHERE match_id = ANY(:ids)` để loại bỏ các trận đã lưu.

---

## 4. Thiết kế cơ sở dữ liệu PostgreSQL

Sử dụng mô hình **Relational + `JSONB` hybrid** để vừa lọc/sắp xếp nhanh theo chỉ mục B-Tree, vừa lưu nguyên cấu trúc lồng sâu của Riot API:

```sql
CREATE TABLE players (
    puuid            VARCHAR(78) PRIMARY KEY,
    region           VARCHAR(10) NOT NULL,
    game_name        VARCHAR(64) NOT NULL,
    tag_line         VARCHAR(16) NOT NULL,
    profile_icon_id  INTEGER,
    summoner_level   INTEGER,
    solo_tier        VARCHAR(16),
    solo_rank        VARCHAR(8),
    solo_lp          INTEGER NOT NULL DEFAULT 0,
    solo_wins        INTEGER NOT NULL DEFAULT 0,
    solo_losses      INTEGER NOT NULL DEFAULT 0,
    last_synced_at   TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_players_riotid
    ON players (region, LOWER(game_name), LOWER(tag_line));

CREATE TABLE matches (
    match_id         VARCHAR(32) PRIMARY KEY,
    region           VARCHAR(10) NOT NULL,
    queue_id         INTEGER NOT NULL,
    game_creation    BIGINT NOT NULL,
    game_duration    INTEGER NOT NULL,
    patch_version    VARCHAR(16) NOT NULL,
    winning_team_id  SMALLINT NOT NULL,
    teams_jsonb      JSONB NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE match_participants (
    match_id          VARCHAR(32) NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    puuid             VARCHAR(78) NOT NULL,
    riot_id_name      VARCHAR(64),
    riot_id_tagline   VARCHAR(16),
    team_id           SMALLINT NOT NULL,
    team_position     VARCHAR(16),
    champion_id       INTEGER NOT NULL,
    win               BOOLEAN NOT NULL,
    kills             SMALLINT NOT NULL,
    deaths            SMALLINT NOT NULL,
    assists           SMALLINT NOT NULL,
    cs_total          SMALLINT NOT NULL,
    gold_earned       INTEGER NOT NULL,
    damage_to_champs  INTEGER NOT NULL,
    vision_score      SMALLINT NOT NULL,
    items_jsonb       JSONB NOT NULL,
    runes_jsonb       JSONB NOT NULL,
    spells_jsonb      JSONB NOT NULL,
    game_creation     BIGINT NOT NULL,
    PRIMARY KEY (match_id, puuid)
);

CREATE INDEX idx_mp_puuid_recent
    ON match_participants (puuid, game_creation DESC);

CREATE INDEX idx_mp_puuid_champ
    ON match_participants (puuid, champion_id);

CREATE TABLE match_timelines (
    match_id         VARCHAR(32) PRIMARY KEY REFERENCES matches(match_id) ON DELETE CASCADE,
    interval_ms      INTEGER NOT NULL DEFAULT 60000,
    frames_jsonb     JSONB NOT NULL,
    events_jsonb     JSONB NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE static_assets (
    patch_version    VARCHAR(16) NOT NULL,
    lang             VARCHAR(10) NOT NULL DEFAULT 'vi_VN',
    champions_jsonb  JSONB NOT NULL,
    items_jsonb      JSONB NOT NULL,
    runes_jsonb      JSONB NOT NULL,
    spells_jsonb     JSONB NOT NULL,
    synced_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (patch_version, lang)
);
```

---

## 5. Đặc tả REST API (Flask Blueprints)

Tất cả endpoint sử dụng tiền tố `/api/v1`, trả về `Content-Type: application/json`, và dùng format lỗi thống nhất:

```json
{
  "error": {
    "code": "SYNC_COOLDOWN_ACTIVE",
    "message": "Vui lòng đợi thêm 85 giây trước khi đồng bộ lại.",
    "retryAfterSeconds": 85
  }
}
```

### 5.1. Danh sách Endpoint bắt buộc

| Method & Path | Tham số / Body | Mã trạng thái | Mô tả hành vi |
| :--- | :--- | :--- | :--- |
| `GET /api/v1/health` | Không có | `200` | Kiểm tra trạng thái Flask app, kết nối PostgreSQL và Redis |
| `GET /api/v1/players/<region>/<game_name>/<tag_line>` | Path: `region`, `game_name`, `tag_line` | `200`, `400`, `404` | Tra cứu từ Redis/DB; nếu chưa có thì gọi Riot Account-V1 + Summoner-V4 + League-V4, lưu vào DB rồi trả về kèm cờ `canSync` và `cooldownRemainingSec` |
| `POST /api/v1/players/<puuid>/sync` | Body JSON: `{"region": "vn2", "count": 20, "queueId": 420}` | `202`, `404`, `429` | Kiểm tra cooldown 120 giây (lưu Redis/DB). Nếu hợp lệ, đẩy job vào hàng đợi đồng bộ trận mới (trả `jobId`, `status: "queued"`; hỗ trợ chế độ chạy đồng bộ trong `TestConfig`) |
| `GET /api/v1/players/<puuid>/matches` | Query: `cursor`, `limit` (1–50, mặc định 20), `queueId`, `championId` | `200`, `400`, `404` | Trả danh sách trận theo `cursor-based pagination` dựa trên `game_creation`, kèm `summary` (số trận, tỷ lệ thắng, KDA trung bình, CS/phút) và tóm tắt 10 người chơi |
| `GET /api/v1/matches/<match_id>/review` | Query: `region` (mặc định suy từ tiền tố `match_id`), `focusPuuid` | `200`, `404`, `502` | Trả bảng điểm 2 đội + 10 người chơi và dữ liệu `timeline` (Gold Diff, XP Diff theo từng phút + sự kiện lớn). Nếu `match_timelines` chưa có, tự động lazy-fetch từ Riot API và lưu vĩnh viễn |
| `GET /api/v1/static/<patch>/catalog` | Query: `lang` (mặc định `vi_VN`). Hỗ trợ `<patch>=latest` | `200`, `404` | Trả bản đồ ID → tên + URL ảnh CDN cho tướng, trang bị, ngọc, phép bổ trợ. Đặt header `Cache-Control: public, max-age=86400` |

### 5.2. Hợp đồng JSON mẫu

**`GET /api/v1/players/<puuid>/matches?limit=20`**

```json
{
  "nextCursor": "1763701200000",
  "summary": {
    "games": 20,
    "wins": 12,
    "winRate": 60.0,
    "avgKda": 3.45,
    "avgCsPerMin": 7.82
  },
  "matches": [
    {
      "matchId": "VN2_492817261",
      "queueId": 420,
      "gameCreation": 1763712000000,
      "gameDuration": 1842,
      "patch": "16.23",
      "player": {
        "puuid": "sample-puuid",
        "championId": 157,
        "teamPosition": "MIDDLE",
        "win": true,
        "kills": 9,
        "deaths": 3,
        "assists": 7,
        "kda": 5.33,
        "csTotal": 248,
        "csPerMin": 8.08,
        "items": [3153, 3031, 6673, 3006, 3026, 0, 3363],
        "spells": [4, 14],
        "keystoneId": 8008
      },
      "participants": [
        {
          "puuid": "sample-puuid",
          "teamId": 100,
          "championId": 157,
          "riotId": "Player1#VN2"
        }
      ]
    }
  ]
}
```

**`GET /api/v1/matches/<match_id>/review`**

```json
{
  "matchId": "VN2_492817261",
  "queueId": 420,
  "gameDuration": 1842,
  "patch": "16.23",
  "teams": [
    { "teamId": 100, "win": true, "barons": 1, "dragons": 3, "towers": 8 },
    { "teamId": 200, "win": false, "barons": 0, "dragons": 1, "towers": 3 }
  ],
  "participants": [],
  "timeline": {
    "intervalMs": 60000,
    "frames": [
      { "minute": 10, "blueGoldDiff": 850, "blueXpDiff": 420 },
      { "minute": 15, "blueGoldDiff": 2400, "blueXpDiff": 1150 }
    ],
    "keyEvents": [
      {
        "timestampMs": 912000,
        "type": "ELITE_MONSTER_KILL",
        "monsterType": "RIFTHERALD",
        "killerTeamId": 100
      }
    ]
  }
}
```

---

## 6. Yêu cầu kiểm thử hàm với `pytest`

Toàn bộ kiểm thử Python phải chạy độc lập, **không gọi Riot API thật** (dùng `responses` hoặc `pytest-mock` để giả lập HTTP response) nhằm đảm bảo chạy nhanh, lặp lại ổn định và không tốn API quota.

### 6.1. Cấu hình `pytest.ini`

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --strict-markers --cov=app --cov-report=term-missing
```

### 6.2. Các nhóm test case bắt buộc

| Nhóm kiểm thử | Tệp test | Kịch bản bắt buộc phải pass |
| :--- | :--- | :--- |
| Routing | `tests/unit/test_routing.py` | Kiểm tra `vn2` ánh xạ `account -> asia`, `match -> sea`, `platform -> vn2`; kiểm tra `kr`, `euw1`, `na1`; kiểm tra ném `ValueError` khi region không hợp lệ |
| Riot HTTP Client | `tests/unit/test_riot_client.py` | Xác nhận gắn header `X-Riot-Token`; xử lý `404` trả `None`/custom error; xử lý `429` đọc `Retry-After` và retry thành công; ném lỗi `RiotRateLimitError` khi vượt số lần retry |
| Data Dragon Service | `tests/unit/test_ddragon_service.py` | Parse `versions.json` lấy bản mới nhất; ánh xạ đúng `championId` (khóa số `key`) sang tên và URL ảnh; ánh xạ `item.json` và `runesReforged.json` |
| Review & Timeline Parser | `tests/unit/test_review_service.py` | Tính đúng `kda` khi `deaths == 0` (không chia cho 0); tính `csPerMin`; tính `blueGoldDiff` và `blueXpDiff` từng phút từ mảng `frames` của `match-v5/timeline`; lọc `keyEvents` (Baron, Rồng, Sứ Giả, phá trụ) |
| Sync & Deduplication | `tests/integration/test_players_api.py` | Gọi `GET /players/...` lưu DB; gọi `POST /sync` 2 lần liên tiếp — lần 1 trả `202` và bỏ qua `match_id` đã tồn tại trong DB, lần 2 trả `429` kèm `retryAfterSeconds`; kiểm tra `cursor` pagination và lọc `championId`/`queueId` |
| Match Review API | `tests/integration/test_matches_api.py` | Gọi `GET /matches/<id>/review` lần đầu tự lazy-fetch `timeline` và lưu DB; gọi lần 2 đọc hoàn toàn từ DB (0 lần gọi Riot API) |
| Static Catalog API | `tests/integration/test_static_api.py` | Trả `200` với `latest` và patch cụ thể; trả `404` với patch không tồn tại; có header `Cache-Control` |

### 6.3. Lệnh xác minh `pytest`

```bash
pytest
```

Tiêu chí đạt: **100% test case pass**, độ phủ kiểm thử (line coverage) đạt tối thiểu **85%** trên `app/services/` và `app/api/`.

---

## 7. Yêu cầu kiểm thử API Endpoint với Postman & Newman Script

Antigravity phải tạo sẵn bộ kiểm thử API tự động gồm 3 tệp trong `postman/` và `scripts/` để kiểm tra toàn bộ luồng end-to-end trên server Flask đang chạy.

### 7.1. Biến môi trường (`postman/local.postman_environment.json`)

| Biến | Giá trị mẫu | Mô tả |
| :--- | :--- | :--- |
| `baseUrl` | `http://127.0.0.1:5000` | Địa chỉ Flask server local |
| `region` | `vn2` | Máy chủ kiểm thử |
| `gameName` | `Player1` | Tên Riot ID mẫu (seed sẵn hoặc mock) |
| `tagLine` | `VN2` | TagLine mẫu |
| `puuid` | *(tự động điền từ test script)* | Lưu sau khi gọi `GET /players/...` |
| `matchId` | *(tự động điền từ test script)* | Lưu từ phần tử đầu của `GET /matches` |
| `nextCursor` | *(tự động điền từ test script)* | Dùng để kiểm thử trang thứ 2 |

### 7.2. Chuỗi Request & Test Assertions (`postman/lol-match-history.postman_collection.json`)

Collection phải chạy tuần tự 7 bước với các `pm.test(...)` assertion cụ thể:

1. **Health Check (`GET {{baseUrl}}/api/v1/health`)**: Assert status `200`, `json.status === "ok"`, `json.database === "up"`.
2. **Get Player Profile (`GET {{baseUrl}}/api/v1/players/{{region}}/{{gameName}}/{{tagLine}}`)**: Assert status `200`, tồn tại `puuid`, `soloTier`, `canSync`; lưu `pm.environment.set("puuid", json.puuid)`.
3. **Trigger Sync (`POST {{baseUrl}}/api/v1/players/{{puuid}}/sync`)**: Assert status `202`, tồn tại `jobId`.
4. **Verify Sync Cooldown (`POST {{baseUrl}}/api/v1/players/{{puuid}}/sync`)**: Gọi ngay lần 2 và assert status `429`, `json.error.code === "SYNC_COOLDOWN_ACTIVE"`, `json.error.retryAfterSeconds > 0`.
5. **Get Match History Page 1 (`GET {{baseUrl}}/api/v1/players/{{puuid}}/matches?limit=5`)**: Assert status `200`, `matches` là mảng, kiểm tra đủ trường `championId`, `items`, `kda`, `csPerMin`; lưu `matchId` và `nextCursor`.
6. **Get Match Review & Timeline (`GET {{baseUrl}}/api/v1/matches/{{matchId}}/review?focusPuuid={{puuid}}`)**: Assert status `200`, `teams.length === 2`, `participants.length === 10`, `timeline.frames` là mảng có `blueGoldDiff` và `blueXpDiff`.
7. **Get Static Catalog (`GET {{baseUrl}}/api/v1/static/latest/catalog?lang=vi_VN`)**: Assert status `200`, có `champions`, `items`, `runes`, `spells` và header `Cache-Control`.

### 7.3. Script chạy Newman (`scripts/run_newman.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

COLLECTION="postman/lol-match-history.postman_collection.json"
ENVIRONMENT="postman/local.postman_environment.json"
REPORT_DIR="reports/newman"

mkdir -p "$REPORT_DIR"

if ! command -v newman >/dev/null 2>&1; then
  echo "Lỗi: chưa cài đặt newman. Hãy chạy: npm install -g newman"
  exit 1
fi

newman run "$COLLECTION" \
  -e "$ENVIRONMENT" \
  --reporters cli,junit \
  --reporter-junit-export "$REPORT_DIR/junit-report.xml" \
  --bail

echo "Tất cả API endpoint tests (Newman) đã pass!"
```

---

## 8. Thứ tự triển khai và tiêu chí nghiệm thu cho Antigravity

Antigravity thực hiện tuần tự 6 bước dưới đây, chỉ chuyển sang bước tiếp theo khi bước hiện tại đã kiểm chứng thành công:

1. **Bước 1 — Khởi tạo dự án & hạ tầng local:** Tạo cấu trúc thư mục, `requirements.txt`, `.env.example`, `docker-compose.yml` (PostgreSQL + Redis), `app/__init__.py`, `app/config.py`, `app/extensions.py`.
2. **Bước 2 — Models & Migration:** Viết 5 SQLAlchemy models khớp hoàn toàn với DDL ở Mục 4, khởi tạo Alembic migration và chạy `flask db upgrade`.
3. **Bước 3 — Tầng Services:** Triển khai `routing.py`, `riot_client.py` (có xử lý `429` và `Retry-After`), `ddragon_service.py`, `sync_service.py` (có deduplication và cooldown 120s), `review_service.py` (tính KDA, CS/phút, Gold/XP Diff).
4. **Bước 4 — Tầng Flask API Blueprints:** Xây dựng 6 endpoint theo đúng hợp đồng JSON ở Mục 5, kèm error handler tập trung và CLI command `flask seed-demo` để nạp dữ liệu mẫu (1 người chơi + 10 trận + 1 timeline + 1 static catalog) phục vụ chạy Newman offline không cần key Riot thật.
5. **Bước 5 — Viết và chạy `pytest`:** Hoàn thiện toàn bộ unit test và integration test ở Mục 6; chạy `pytest` đảm bảo 100% pass và coverage >= 85%.
6. **Bước 6 — Tạo Postman Collection & chạy Newman:** Xuất `lol-match-history.postman_collection.json`, `local.postman_environment.json`, `scripts/run_newman.sh`; chạy `flask seed-demo`, khởi động Flask server ở nền và thực thi `bash scripts/run_newman.sh` đảm bảo tất cả assertion pass với exit code `0`.

---

## 9. Nguồn tham khảo

1. [Riot Developer Portal — APIs Reference](https://developer.riotgames.com/apis)
2. [Riot Developer Portal — League of Legends & Data Dragon Docs](https://developer.riotgames.com/docs/lol)
3. [Riot Developer Portal — Rate Limiting & API Key Security](https://developer.riotgames.com/docs/portal)
4. [Riot Developer Relations — League of Legends Platform Routing](https://support-developer.riotgames.com/hc/en-us/articles/22698698001939-League-of-Legends)
5. [Riot API Libraries — Data Dragon Guide](https://riot-api-libraries.readthedocs.io/en/latest/ddragon.html)
6. [DarkIntaqt — Platforms, Regions and How to Route Riot API Requests](https://darkintaqt.com/blog/routing)
7. [Coachless — League of Legends Review Tool](https://coachless.gg/review)
