# Kế Hoạch Phân Công Công Việc — Dự Án RiftReview (Tuần 12–15)

> **Quy mô nhóm:** 2 thành viên (**Vũ Hải Linh**, **Đinh Phúc Hưng**)  
> **Phạm vi:** Triển khai hệ thống Lịch sử đấu & Phân tích LMHT (Flask REST API `/api/v1`, PostgreSQL + Redis, Riot API, LightGBM, Next.js 15 BFF, Pytest/Newman/Locust).

---

## 1. Phân chia vai trò tổng thể

| Thành viên | Vai trò chính | Phạm vi kỹ thuật phụ trách |
| :--- | :--- | :--- |
| **Vũ Hải Linh** | **Backend Core, Security & QA/Testing** | - Kiến trúc Flask App Factory, SQLAlchemy Models, Alembic Migrations & DDL PostgreSQL.<br>- Bảo mật OAuth 2.0 `client_credentials` (JWT RS256, Revocation), RFC 9457 Error Handling, `Idempotency-Key`, Cursor Pagination.<br>- Tài liệu `openapi.yaml` + Swagger UI.<br>- Kiểm thử tự động (`pytest` >= 85% coverage, Postman/Newman E2E, Locust Load Test theo SLO). |
| **Đinh Phúc Hưng** | **Riot Integration, ML Pipeline & Frontend** | - Định tuyến Riot API, `RiotClient` (Token Bucket 2 tầng + xử lý `429 Retry-After`), Async Sync Jobs (RQ Worker / Thread), Data Dragon Catalog.<br>- Pipeline Machine Learning: Crawler Bot (`flask crawl-matches`), Feature Engineering (`initial_win_rate`, scaling, Leave-One-Match-Out), huấn luyện LightGBM & tính Player Impact (WPA%).<br>- Frontend Next.js 15 + Tailwind (BFF Proxy `/api/lol/*`, đồ thị Win Probability tương tác, Minimap vị trí 10 tướng). |

---

## 2. Phân công chi tiết theo từng tuần (Tuần 12 – Tuần 15)

### Tuần 12 *(Hiện tại)* — Phân tích yêu cầu, Thiết kế API & Khởi tạo Repo
**Mục tiêu chung:** Hoàn thiện Project Brief, Resource Model, ERD, Kiến trúc, `openapi.yaml`, Repo + Backlog và Demo tối thiểu 3 API operations.

| Thành viên | Đầu việc cụ thể | Sản phẩm bàn giao / Bằng chứng |
| :--- | :--- | :--- |
| **Vũ Hải Linh** | - Khởi tạo Git repository, cấu trúc thư mục Flask, `README.md` và GitHub Issues/Backlog.<br>- Thiết kế Resource Model, ERD (Chen's Notation), DDL PostgreSQL và viết hợp đồng `openapi.yaml` + tích hợp Swagger UI.<br>- Dựng khung API mẫu (mock/seed) cho tối thiểu 3 operations (`POST /oauth/tokens`, `GET /players/{puuid}/matches`, `POST /players/{puuid}/sync-jobs`) + lỗi chuẩn RFC 9457.<br>- Chuẩn bị phần slide Thiết kế API, Bảo mật & Trade-offs. | - Git repo + `README.md` + Backlog.<br>- File `openapi.yaml` chạy được trên Swagger UI.<br>- Demo sống 3+ API endpoints. |
| **Đinh Phúc Hưng** | - Viết Project Brief (Bài toán, API Consumers, 5 Use Cases, MVP vs Out of Scope) và vẽ Kiến trúc hệ thống.<br>- Nghiên cứu và chuẩn hóa quy tắc định tuyến Riot API (`platform` / `asia` / `sea`), giới hạn rate limit và cấu trúc dữ liệu Data Dragon.<br>- Thiết kế luồng ML Pipeline (Crawler Bot, Feature Engineering, LightGBM) và wireframe luồng màn hình Frontend.<br>- Chuẩn bị phần slide Bài toán, Kiến trúc hệ thống & ML Pipeline. | - Tài liệu đặc tả đầy đủ (Project Brief + Thiết kế).<br>- Slide thuyết trình 6–8 trang (phối hợp cùng Linh).<br>- Script `flask seed-demo` tạo dữ liệu mẫu phục vụ demo. |

---

### Tuần 13 — Hoàn thiện Backend Core & Tích hợp Riot API
**Mục tiêu chung:** Hoàn thiện toàn bộ tầng Backend Core, kết nối Riot API/Data Dragon an toàn và đạt độ phủ kiểm thử đơn vị/tích hợp `>= 85%`.

| Thành viên | Đầu việc cụ thể | Sản phẩm bàn giao / Bằng chứng |
| :--- | :--- | :--- |
| **Vũ Hải Linh** | - Triển khai đầy đủ SQLAlchemy Models (`players`, `matches`, `match_participants`, `match_timelines`, `static_assets`) và Alembic Migrations.<br>- Hoàn thiện OAuth 2.0 JWT RS256, kiểm tra scope, thu hồi `jti` trên Redis và object-level authorization cho `sync-jobs`.<br>- Triển khai chuẩn lỗi RFC 9457, `Idempotency-Key` (Redis TTL 24h) và Keyset Cursor Pagination ký HMAC.<br>- Viết bộ test `pytest` cho `app/api/` (Auth, RFC 9457, Idempotency, Cursor Pagination). | - PR/Commit Backend Core & DDL Postgres.<br>- Báo cáo `pytest --cov=app/api` pass 100%, coverage `>= 85%`. |
| **Đinh Phúc Hưng** | - Triển khai `RiotClient` dùng `httpx`, Token Bucket 2 tầng trên Redis và cơ chế retry theo header `Retry-After`.<br>- Xây dựng `player_service`, `sync_service` (cooldown 120s, deduplication `match_id`, hàng đợi RQ Worker / Thread fallback cho DevLite).<br>- Xây dựng `ddragon_service` (cache catalog theo patch, hỗ trợ `ETag` & `Cache-Control`) và lazy-fetch `match_timelines`.<br>- Viết bộ test `pytest` (mock bằng `respx` + `fakeredis`) cho `app/services/`. | - PR/Commit Riot Integration, Sync & DDragon.<br>- Báo cáo `pytest --cov=app/services` pass 100%, coverage `>= 85%`. |

---

### Tuần 14 — Hoàn thiện ML Pipeline & Frontend Next.js + Tailwind
**Mục tiêu chung:** Thu thập 200+ trận thật, huấn luyện xong LightGBM tích hợp vào `/review`, và hoàn thiện giao diện Web chạy E2E.

| Thành viên | Đầu việc cụ thể | Sản phẩm bàn giao / Bằng chứng |
| :--- | :--- | :--- |
| **Vũ Hải Linh** | - Triển khai endpoint `GET /api/v1/matches/{matchId}/review` ghép nối dữ liệu bảng điểm, timeline và đầu ra `analytics` từ ML Engine.<br>- Dựng lớp **Next.js 15 BFF Proxy** (`/api/lol/*`) tự động quản lý JWT RS256 ở server-side, chống lộ secret và xử lý CORS.<br>- Xây dựng trang tra cứu Riot ID, hồ sơ người chơi, nút đồng bộ (hiển thị cooldown) và danh sách lịch sử đấu phân trang cursor + bộ lọc (`queueId`, `championId`).<br>- Viết unit test cho endpoint `/review` và kiểm tra build Next.js TypeScript strict. | - PR/Commit `/review` API & Next.js BFF + trang History.<br>- `npm run build` 0 lỗi TypeScript. |
| **Đinh Phúc Hưng** | - Xây dựng & chạy Crawler Bot (`flask crawl-matches`) thu thập `200+` trận xếp hạng thật (có đủ timeline & tọa độ) vào DB.<br>- Triển khai `stats_store.py` & `features.py` (`initial_win_rate` 5 đường, đường cong scaling 3 pha, Leave-One-Match-Out) và huấn luyện LightGBM (`flask train-win-model`), tính `eventTimeline` & Player Impact (WPA%).<br>- Xây dựng trang **Match Review** trên Next.js + Tailwind: bảng điểm 10 người, đồ thị Win Probability tương tác 2 chiều, Highlights và Minimap vị trí 10 tướng + túi đồ theo mốc thời gian. | - Log crawl 200+ trận & file `win_prob_model.pkl` kèm metrics (AUC, LogLoss).<br>- Màn hình Match Review chạy E2E thực tế. |

---

### Tuần 15 — Kiểm thử toàn diện, Đóng gói & Bảo vệ cuối kỳ
**Mục tiêu chung:** Hoàn tất kiểm thử hợp đồng (Newman), kiểm thử tải đạt SLO (Locust), đóng gói Docker Compose/DevLite và sẵn sàng bảo vệ.

| Thành viên | Đầu việc cụ thể | Sản phẩm bàn giao / Bằng chứng |
| :--- | :--- | :--- |
| **Vũ Hải Linh** | - Hoàn thiện Postman Collection v2.1 và chạy Newman (`bash scripts/run_newman.sh`) đạt **11/11 requests, 21/21 assertions pass**.<br>- Triển khai & chạy Locust Load Test (`tests/load/locustfile.py`, 80% đọc / 20% ghi) tinh chỉnh cache/query để đạt SLO (`error_rate < 1%`, `p95 < 300ms`, `p99 < 800ms`).<br>- Rà soát bảo mật cuối cùng (không lộ `RIOT_API_KEY`, stack trace, `alg: none`) và cập nhật `openapi.yaml` khớp 100% với code. | - Báo cáo JUnit `reports/newman/junit-report.xml`.<br>- Báo cáo CSV/SLO Locust đạt chuẩn (exit code `0`). |
| **Đinh Phúc Hưng** | - Hoàn thiện `docker-compose.yml` (Flask + PostgreSQL + Redis + RQ + Next.js) và kiểm tra kịch bản dự phòng `DevLiteConfig` (SQLite + `fakeredis`) + `flask seed-demo` chạy offline mượt mà.<br>- Tối ưu hiệu năng hiển thị Frontend, chụp ảnh/quay video backup luồng E2E.<br>- Tổng hợp tài liệu báo cáo cuối kỳ và slide bảo vệ (phối hợp cùng Linh luyện tập kịch bản demo & trả lời Q&A). | - Bản chạy hoàn chỉnh trên Docker Compose & DevLite.<br>- Tài liệu báo cáo + Slide bảo vệ cuối kỳ. |

---

## 3. Bảng Backlog & Issues đề xuất

| Issue | Hạng mục công việc | Phụ trách | Tuần | Ưu tiên | Định nghĩa hoàn thành (DoD) |
| :---: | :--- | :--- | :---: | :---: | :--- |
| `#01` | Khởi tạo Repo, Flask Factory, `README.md` & Backlog | Vũ Hải Linh | 12 | Cao | Chạy được `flask run`, có đủ nhánh `main`/`dev` và tài liệu setup |
| `#02` | Viết `openapi.yaml` + Swagger UI & Demo 3 API operations | Vũ Hải Linh | 12 | Cao | Swagger UI render không lỗi; demo được 3 endpoint + lỗi RFC 9457 |
| `#03` | Hoàn thiện Project Brief, Kiến trúc & `flask seed-demo` | Đinh Phúc Hưng | 12 | Cao | Tài liệu đặc tả đầy đủ hình ảnh, lệnh seed tạo được dữ liệu demo |
| `#04` | SQLAlchemy Models, DDL PostgreSQL & Alembic Migrations | Vũ Hải Linh | 13 | Cao | `flask db upgrade` chạy sạch trên cả Postgres và SQLite DevLite |
| `#05` | OAuth 2.0 JWT RS256, Revocation, RFC 9457, Idempotency & Cursor | Vũ Hải Linh | 13 | Cao | Pass toàn bộ test bảo mật, replay `202`, conflict `409`, invalid cursor `400` |
| `#06` | `RiotClient` (Routing, Token Bucket 2 tầng, 429 Retry-After) | Đinh Phúc Hưng | 13 | Cao | Mock test `respx` xác nhận không vượt rate limit và xử lý đúng `429` |
| `#07` | Async Sync Jobs (Cooldown 120s, Dedup), RQ Worker & DDragon | Đinh Phúc Hưng | 13 | Cao | Đồng bộ không trùng `match_id`, DDragon trả đúng `ETag` / `304` |
| `#08` | Pytest Coverage >= 85% (`app/api` & `app/services`) | Cả 2 thành viên | 13 | Cao | `pytest --cov-fail-under=85` trả exit code `0` |
| `#09` | Crawler Bot thu thập 200+ trận thật (kèm Timeline + tọa độ) | Đinh Phúc Hưng | 14 | Cao | DB có >= 200 trận hợp lệ (không remake), lưu đủ `frames` & `events` |
| `#10` | Feature Engineering (Leave-One-Match-Out) & LightGBM + WPA% | Đinh Phúc Hưng | 14 | Cao | Xuất model `win_prob_model.pkl`, log AUC/LogLoss, không bị target leakage |
| `#11` | API `GET /matches/{matchId}/review` & Next.js BFF + Trang History | Vũ Hải Linh | 14 | Cao | BFF giữ JWT ở server-side; tra cứu, lọc và phân trang hoạt động E2E |
| `#12` | Giao diện Match Review (Win Prob Graph, Highlights, Minimap 10 tướng) | Đinh Phúc Hưng | 14 | Cao | Tương tác chọn mốc thời gian cập nhật đúng túi đồ & vị trí 10 tướng |
| `#13` | Postman Collection v2.1 & Newman CI Script | Vũ Hải Linh | 15 | Cao | 11/11 requests, 21/21 assertions pass; xuất file JUnit XML |
| `#14` | Locust Load Testing & Tối ưu hiệu năng đạt SLO | Vũ Hải Linh | 15 | Cao | `error_rate < 1%`, `p95 < 300ms`, `p99 < 800ms` |
| `#15` | Đóng gói Docker Compose + Kiểm thử chế độ DevLite Offline | Đinh Phúc Hưng | 15 | Trung bình | Khởi chạy sạch từ đầu trên máy mới trong < 3 phút |
| `#16` | Hoàn thiện Báo cáo, Slide bảo vệ & Tổng duyệt Demo | Cả 2 thành viên | 15 | Cao | Chạy thông suốt luồng Core E2E Flow và kịch bản xử lý sự cố |

---

## 4. Quy ước phối hợp cho nhóm 2 người

1. **Quy ước Git Branch:**
   - `main`: chỉ merge code ổn định cuối mỗi tuần (phục vụ chấm bài/demo).
   - `main`: nhánh tích hợp chung.
   - Nhánh tính năng: `feat/linh-<ten-tinh-nang>` và `feat/hung-<ten-tinh-nang>`.
2. **Cross-Review:** Mọi Pull Request vào `main` đều cần thành viên còn lại review nhanh và vượt qua `pytest` trước khi merge.
3. **Điểm đồng bộ cuối tuần (Weekly Checkpoint):**
   - **Cuối Tuần 12:** Chốt cứng schema JSON trong `openapi.yaml` để cả hai code song song không bị lệch contract.
   - **Cuối Tuần 13:** Ghép `app/api` (Linh) + `app/services` (Hưng), chạy chung `pytest` đạt `>= 85%`.
   - **Cuối Tuần 14:** Ghép đầu ra LightGBM (Hưng) vào `/review` và BFF Next.js (Linh), chạy thông luồng giao diện E2E.
   - **Cuối Tuần 15:** Chạy tổng kiểm thử Newman + Locust và duyệt thử kịch bản thuyết trình.