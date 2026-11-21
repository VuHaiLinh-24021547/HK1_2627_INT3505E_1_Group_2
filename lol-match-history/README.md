# RiftReview — Hệ Thống Lịch Sử Đấu & Phân Tích LMHT (Flask + LightGBM + Next.js)

Hệ thống full-stack tra cứu và phân tích lịch sử đấu Liên Minh Huyền Thoại theo phong cách **Coachless Review**:

- **Backend**: Python 3 / **Flask 3**, SQLAlchemy 2 + Alembic, **PostgreSQL 15 + Redis 7** (kèm chế độ `devlite` dùng SQLite + `fakeredis` để chạy ngay không cần Docker).
- **Machine Learning**: **Crawler Bot** thu thập dữ liệu trận đấu + timeline thật từ Riot API, và mô hình **LightGBM** dự đoán **Tỉ lệ thắng theo thời gian (Win Probability)** kết hợp phân tích **Đóng góp của từng người chơi (Player Impact / WPA%)**.
- **Frontend**: **Next.js 15 (App Router, TypeScript)** + **Tailwind CSS**, kết nối an toàn qua Next.js BFF API Proxy.

---

## Tính năng nổi bật

### 1. Backend REST API & Tích hợp Riot API
- **Định tuyến Riot API chính xác** (`app/services/routing.py`): `vn2` → `account-v1` qua `asia.api.riotgames.com`, `match-v5` qua `sea.api.riotgames.com`, `summoner-v4`/`league-v4` qua `vn2.api.riotgames.com` (hỗ trợ đầy đủ 14 khu vực).
- **Rate Limiting & 429 Handling** (`app/services/riot_client.py`): Token Bucket 2 tầng (`20 req/1s`, `100 req/120s`) trên Redis, đọc `Retry-After` khi nhận `429` và retry có giới hạn; tuyệt đối không log/lộ `RIOT_API_KEY`.
- **Đồng bộ & chống trùng lặp** (`app/services/sync_service.py`): Cooldown 120 giây/người chơi, truy vấn deduplication `match_id` trước khi gọi Match-V5 detail, hỗ trợ 3 chế độ thực thi (`rq`, `thread`, `inline`).
- **Data Dragon** (`app/services/ddragon_service.py`): Đồng bộ `versions.json`, `champion.json`, `item.json`, `runesReforged.json`, `summoner.json` (`vi_VN`, `en_US`), cache Redis + HTTP `Cache-Control` + `ETag` (`304 Not Modified`).
- **Chuẩn REST API sản xuất**:
  - Versioning `/api/v1/...`, tài nguyên số nhiều, không động từ trong path.
  - **OAuth 2.0 + JWT (RS256)**: `POST /api/v1/oauth/tokens` (`client_credentials`, bật ở dev/test), `POST /api/v1/oauth/revocations` (RFC 7009); xác thực `alg` allowlist (`RS256`/`ES256`), `exp`, `nbf`, `iss`, `aud`, `sub`, `jti`, phân quyền theo scope (`players:read`, `players:sync`, `matches:read`, `static:read`) và object-level authorization trên `GET /api/v1/sync-jobs/<jobId>`.
  - **Idempotency-Key (UUIDv4)** trên `POST /api/v1/players/<puuid>/sync-jobs` (replay `202` nếu cùng payload, `422` nếu khác payload, `409` nếu đang xử lý).
  - **Cursor-based pagination** mờ (Base64-URL + HMAC) với tie-breaker `(game_creation, match_id)` và allowlist filter/sort.
  - **RFC 9457 Problem Details** (`application/problem+json`) kèm `traceId`, không lộ stack trace.

### 2. Machine Learning Pipeline (`app/ml/`)
- **Crawler Bot (`app/ml/crawler.py`)**: Tự động lấy danh sách seed PUUID từ bậc **Master / Grandmaster / Challenger** (`RANKED_SOLO_5x5`) hoặc từ `--seed "GameName#TAG"`, duyệt BFS snowball qua 10 người chơi trong mỗi trận, bỏ qua remake (`< 10 phút`), deduplicate `match_id`, lưu đầy đủ `matches`, `match_participants` và `match_timelines`.
- **Tỉ lệ thắng khởi đầu (`initial_win_rate`) & Scaling theo thời gian (`app/ml/stats_store.py`)**:
  - Tính tỉ lệ thắng từng kèo matchup cùng đường (`TOP`, `JUNGLE`, `MIDDLE`, `BOTTOM`, `UTILITY`) có Bayesian smoothing; `initial_win_rate` là trung bình 5 kèo cùng đường.
  - Tính đường cong tỉ lệ thắng theo 3 giai đoạn trận đấu (`early < 25m`, `mid 25–32m`, `late >= 33m`) và độ dốc `scaling_slope = late_wr - early_wr` giúp tỉ lệ thắng phản ánh sức mạnh scale của đội hình (ví dụ Smolder/Kayle về late vs Pyke/Renekton đầu game) ngay cả khi không có sự kiện lớn.
- **LightGBM & Đóng góp người chơi (`app/ml/features.py`, `app/ml/model.py`)**:
  - 18 đặc trưng theo thời gian (thời gian, `initial_win_rate`, scaling diff, chênh lệch vàng/XP/CS/cấp độ, tốc độ vàng/XP mỗi phút, chênh lệch hạ gục, Baron, Rồng, Sứ Giả, Sâu Hư Không, Trụ, Nhà Lính).
  - Chia train/val tách biệt hoàn toàn theo `match_id` và áp dụng **Leave-One-Match-Out** cho thống kê matchup/scaling để loại bỏ target leakage.
  - Nội suy và chạy LightGBM tại **từng timestamp sự kiện chính xác đến giây (`MM:SS`)** (`eventTimeline`) + tự động chọn tối đa 5 bước ngoặt lớn (`highlights`).
  - Phân bổ biến thiên tỉ lệ thắng từng phút cho 10 người chơi theo 3 thành phần: **Giao tranh (Combat)**, **Mục tiêu (Objective)** và **Đi đường/Farm (Laning)**.

### 3. Frontend Next.js + Tailwind CSS (`frontend/`)
- **BFF Auth Proxy (`/api/lol/[...path]`)**: Next.js server tự lấy và cache JWT từ Flask backend bằng `OAUTH_CLIENT_ID`/`OAUTH_CLIENT_SECRET`, không lộ secret ra trình duyệt và không gặp lỗi CORS.
- **Trang tra cứu & Hồ sơ người chơi**: Tìm Riot ID theo khu vực, hiển thị hạng Đơn/Đôi, thống kê tổng hợp, nút **Đồng bộ trận mới** (gắn `Idempotency-Key` + đếm ngược cooldown 120s + polling job), lọc theo chế độ & tướng, phân trang cursor.
- **Trang Chi tiết hậu trận (Coachless Review)**:
  - **Đồ thị 2 màu tương tác (Win Probability / Contribution)** có thể **bấm hoặc kéo tại bất kỳ vị trí nào** để ghim đường gióng dọc, hiển thị hộp nổi `Win Probability + Time MM:SS` kèm icon sự kiện, và **tự động cuộn đồng bộ 2 chiều** với cột **Timeline Events (`MM:SS`)** bên phải + 5 thẻ **Turning Points** bấm nhanh bên dưới.
  - Khối **Tỉ lệ thắng khởi đầu theo 5 đường**, bảng **Đóng góp 10 người chơi (Impact %)**, bảng điểm 10 người chơi (thanh sát thương, KDA, CS/phút, trang bị, phép, ngọc) và lịch sử mua trang bị.

---

## Cấu trúc thư mục

```text
lol-match-history/
├── app/
│   ├── api/                 # Flask Blueprints (/api/v1), RFC 9457 errors, Idempotency-Key, schemas
│   ├── auth/                # RS256 key management, JWT issue/verify/revocation, scope decorators
│   ├── ml/                  # crawler.py, stats_store.py, features.py, model.py (LightGBM + WPA)
│   ├── models/              # SQLAlchemy 2 models (players, matches, match_participants, match_timelines, static_assets)
│   ├── services/            # routing, riot_client, ddragon_service, player_service, sync_service, review_service
│   ├── workers/             # RQ sync_worker
│   └── cli.py               # Flask CLI commands
├── frontend/                # Next.js 15 + Tailwind CSS + TypeScript
│   └── src/
│       ├── app/             # App Router pages (/, /players/[region]/[riotId], /matches/[matchId], /api/lol/[...path])
│       ├── components/      # Navbar, SearchBar, PlayerDashboard, MatchCard, MatchReviewView, TimelineChart
│       └── lib/             # Server BFF client, types, formatters
├── migrations/              # Alembic database migrations
├── postman/                 # Postman Collection v2.1 + local environment
├── scripts/                 # run_newman.sh
├── tests/                   # unit/, integration/, load/locustfile.py, fixtures/
├── docker-compose.yml       # PostgreSQL 15 + Redis 7
├── .env.example
└── requirements.txt
```

---

## Khởi chạy nhanh

### 1. Cài đặt Backend

```bash
cd lol-match-history
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Chế độ DevLite (SQLite + fakeredis, không cần Docker)

```bash
APP_CONFIG=devlite FLASK_APP=app:create_app flask db upgrade
APP_CONFIG=devlite FLASK_APP=app:create_app flask seed-demo
APP_CONFIG=devlite FLASK_APP=app:create_app flask run
```

### 3. Chế độ Full Stack (PostgreSQL 15 + Redis 7 + RQ Worker)

```bash
docker compose up -d
APP_CONFIG=dev FLASK_APP=app:create_app flask db upgrade
# Điền RIOT_API_KEY trong .env để đồng bộ dữ liệu thật:
APP_CONFIG=dev FLASK_APP=app:create_app flask sync-ddragon
# Terminal 1: API server
APP_CONFIG=dev FLASK_APP=app:create_app flask run
# Terminal 2: Background worker
APP_CONFIG=dev python -m app.workers.sync_worker
```

### 4. Thu thập dữ liệu thật (Crawler Bot) & Huấn luyện LightGBM

Đảm bảo `RIOT_API_KEY` trong `.env` còn hạn (Development key có hiệu lực 24 giờ từ Riot Developer Portal):

```bash
# Bước 1: Đồng bộ tài nguyên tĩnh Data Dragon (ảnh 170+ tướng, trang bị, ngọc, phép)
APP_CONFIG=devlite FLASK_APP=app:create_app flask sync-ddragon

# Bước 2: Chạy bot crawl trận đấu + timeline thật (lấy seed từ bậc Master/GM/Challenger)
APP_CONFIG=devlite FLASK_APP=app:create_app flask crawl-matches \
  --region vn2 --target-matches 100 --queue 420 --tier master

# Hoặc truyền seed Riot ID cụ thể:
APP_CONFIG=devlite FLASK_APP=app:create_app flask crawl-matches \
  --region vn2 --target-matches 100 --seed "TenNguoiChoi#VN2"

# Bước 3: Huấn luyện LightGBM (lưu tại instance/ml/win_prob_model.pkl)
APP_CONFIG=devlite FLASK_APP=app:create_app flask train-win-model
```

### 5. Khởi chạy Frontend (Next.js + Tailwind CSS)

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Mở trình duyệt tại `http://127.0.0.1:3000` (hoặc trang demo `http://127.0.0.1:3000/players/vn2/Player1-VN2`).

---

## Danh sách CLI Commands (`FLASK_APP=app:create_app`)

| Lệnh | Mô tả |
| :--- | :--- |
| `flask db upgrade` | Áp dụng Alembic migrations vào database |
| `flask seed-demo` | Nạp dữ liệu mẫu offline (`Player1#VN2`, 10 trận, 1 timeline, static catalog) |
| `flask sync-ddragon [--patch VER]` | Tải `champion/item/runes/summoner` (`vi_VN`, `en_US`) từ Data Dragon |
| `flask crawl-matches` | Bot crawl dữ liệu trận đấu + timeline thật từ Riot API vào DB |
| `flask train-win-model` | Huấn luyện LightGBM dự đoán tỉ lệ thắng từng phút & lưu model artifact |
| `flask gen-keys [--overwrite]` | Tạo cặp khoá RSA (RS256) cho JWT trong `instance/keys/` |
| `flask issue-token [--sub ...] [--scopes ...]` | Cấp nhanh access token RS256 để thử API thủ công |

---

## Danh sách Endpoint (`/api/v1`)

| Method & Path | Scope | Mô tả |
| :--- | :--- | :--- |
| `GET /api/v1/health` | Public | Kiểm tra trạng thái app, DB, Redis |
| `POST /api/v1/oauth/tokens` | Client Creds | Cấp JWT RS256 (Dev/Test) |
| `POST /api/v1/oauth/revocations` | Client Creds | Thu hồi JWT theo `jti` (RFC 7009) |
| `GET /api/v1/regions/<region>/players/<gameName>/<tagLine>` | `players:read` | Tra cứu hồ sơ người chơi |
| `POST /api/v1/players/<puuid>/sync-jobs` | `players:sync` | Tạo job đồng bộ trận mới (`Idempotency-Key`, `202` + `Location`) |
| `GET /api/v1/sync-jobs/<jobId>` | `players:sync` | Xem trạng thái job (chỉ chủ job thấy) |
| `GET /api/v1/players/<puuid>/matches` | `matches:read` | Lịch sử đấu phân trang cursor + lọc `queueId`, `championId` |
| `GET /api/v1/matches/<matchId>/review` | `matches:read` | Bảng điểm 10 người + timeline Gold/XP Diff + `analytics` (LightGBM Win Probability, `eventTimeline`, `highlights`, `laneMatchups`, `playerContributions`) |
| `GET /api/v1/static-catalogs/<patch>` | `static:read` | Danh mục tướng/trang bị/ngọc/phép (`latest` hoặc patch cụ thể) |

---

## Kiểm thử

```bash
# 1. Unit & Integration tests (pytest, >= 85% coverage trên app/services & app/api)
pytest

# 2. End-to-End API contract tests (Newman — đảm bảo server đã chạy và seed-demo)
bash scripts/run_newman.sh

# 3. Load test & SLO check (Locust: error_rate < 1%, p95 < 300ms, p99 < 800ms)
locust -f tests/load/locustfile.py --headless -u 20 -r 5 -t 15s \
  --host http://127.0.0.1:5000 --csv=reports/load_test

# 4. Frontend production build & TypeScript check
cd frontend && npm run build
```

---

## Ghi chú thiết kế & bảo mật

- **OAuth 2.0 & JWT**: Hệ thống dùng luồng `client_credentials` giữa Next.js BFF và Flask Resource Server (theo RFC 6749 §4.4.3 không cấp refresh token; hỗ trợ thu hồi token qua `/api/v1/oauth/revocations`). Ở Production (`APP_CONFIG=prod`), tắt `/oauth/tokens` nội bộ và cấu hình `JWT_JWKS_URL` trỏ sang IdP thật.
- **BOLA / Object-level authorization**: Hồ sơ và trận đấu LoL là dữ liệu công khai từ Riot nên phân quyền theo OAuth scope; riêng `sync-jobs` áp dụng kiểm tra chủ sở hữu (`createdBy == sub`) để tránh truy cập chéo giữa các client.
