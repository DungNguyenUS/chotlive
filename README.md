# CHOTLIVE - HỆ THỐNG QUẢN LÝ CHỐT ĐƠN LIVESTREAM FACEBOOK (FANPAGE & TRANG CÁ NHÂN)

ChotLive là hệ thống web application (tối ưu Mobile-First cho điện thoại, máy tính bảng và máy tính) giúp các cửa hàng tại Việt Nam quản lý phiên livestream, tiếp nhận và phân tích bình luận đặt hàng tiếng Việt, bấm **ĐÃ CHỐT** chống trùng đơn, gửi tin nhắn xác nhận đơn hàng qua Messenger và in phiếu chốt đơn (khổ 80mm, A6, A5).

---

## Điểm Nổi Bật Về Kiến Trúc & Tuân Thủ Chính Sách Meta

- **Thống nhất 2 nguồn Livestream hợp pháp**:
  1. **Facebook Fanpage (`FACEBOOK_PAGE`)**: Tích hợp qua Meta Graph API `v21.0`, OAuth, Webhooks (`feed` -> `comment`) và Messenger Private Replies API (`POST /{page-id}/messages` với `recipient.comment_id`).
  2. **Facebook Trang Cá Nhân (`FACEBOOK_PERSONAL`)**: Vì Meta Graph API không cấp quyền tự động đọc bình luận hoặc gửi tin nhắn tự động cho trang cá nhân tiêu chuẩn, hệ thống cung cấp chế độ **`MANUAL_MODE`** minh bạch (nhập nhanh/dán hàng loạt bình luận, tạo sẵn nội dung tin nhắn để sao chép và mở luồng Messenger). Tuyệt đối không dùng scraping trái phép, không lưu mật khẩu Facebook.
- **Minh bạch trạng thái 100%**: Phân biệt rõ ràng `DEMO`, `CONNECTED`, `NEEDS_PERMISSION`, `MANUAL_MODE`, `FAILED`, `MISSING_CREDENTIALS`. Không bao giờ trộn lẫn dữ liệu giả lập thành dữ liệu thật hoặc báo "Đã gửi tin nhắn / Đã in phiếu thành công" khi thực tế chỉ mới mở hộp thoại.
- **Chống trùng đơn tuyệt đối (Concurrency & Idempotency)**: Sử dụng transaction cơ sở dữ liệu kết hợp ràng buộc cứng `UNIQUE(shop_id, comment_id)` và `UNIQUE(shop_id, idempotency_key)`. Hai nhân viên bấm **ĐÃ CHỐT** cùng một bình luận ở cùng một thời điểm chỉ tạo đúng **1 đơn hàng duy nhất**.

---

## Hướng Dẫn Từng Bước (11 Bước Từ Cài Đặt Đến Triển Khai Production)

### 1. Cài đặt Dependencies
```powershell
# Backend (Python 3.9+ / 3.12)
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt

# Frontend (Node.js 18+ / 20+)
cd ..\frontend
npm install
```

### 2. Cấu hình Environment
Sao chép file `.env.example` thành `.env` tại thư mục gốc của dự án:
```powershell
Copy-Item .env.example .env
```
*(Xem chi tiết giải thích từng biến trong `.env.example`)*.

### 3. Khởi động Database và Redis
- **Cách A (Khuyên dùng khi chạy Docker)**:
  ```powershell
  docker compose up -d postgres redis
  ```
- **Cách B (Chạy trực tiếp trên máy Local khi chưa bật Docker Desktop)**:
  Giữ nguyên `DATABASE_URL=sqlite:///./chotlive_dev.db` trong `.env`. Hệ thống tự động bật chế độ SQLite WAL + Foreign Keys `ON` đầy đủ tính năng.

### 4. Chạy Database Migrations
```powershell
cd backend
.\.venv\Scripts\alembic.exe upgrade head
```

### 5. Tạo Tài Khoản & Dữ Liệu Mẫu Development
*(Chỉ chạy trong môi trường `APP_ENV=development`, script tự động từ chối chạy nếu `APP_ENV=production`)*:
```powershell
cd backend
.\.venv\Scripts\python.exe -m app.seed
```
Tài khoản được tạo:
- **Chủ shop (`OWNER`)**: `owner@chotlive.vn` / Mật khẩu: `ChotLive@2026`
- **Nhân viên (`STAFF`)**: `staff@chotlive.vn` / Mật khẩu: `ChotLive@2026`

### 6. Khởi động Backend (Cổng 8000)
```powershell
cd backend
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```
- Swagger OpenAPI Docs: `http://localhost:8000/docs`
- Healthcheck: `http://localhost:8000/api/v1/health`

### 7. Khởi động Frontend (Cổng 3000)
```powershell
cd frontend
npm run dev
```
Mở trình duyệt tại: `http://localhost:3000`

### 8. Chạy Kiểm Thử Tự Động (Backend, Frontend & End-to-End)
```powershell
# 1. Backend Unit & Integration Tests (pytest)
cd backend
.\.venv\Scripts\pytest.exe -v

# 2. Frontend Component & Unit Tests (Vitest)
cd ..\frontend
npm test

# 3. End-to-End Browser Tests (Playwright - cần Backend :8000 và Frontend :3000 đang chạy)
npx playwright test
```

### 9. Sử dụng Mock Integration trong Development
- Khi `APP_ENV=development` và chưa điền `META_APP_ID` / `META_APP_SECRET`, bạn có thể tạo phiên live với nguồn `DEMO` để kiểm thử toàn bộ luồng tiếp nhận bình luận, phân tích mã hàng, bấm **ĐÃ CHỐT**, gửi tin nhắn qua `MockMetaMessengerAdapter` (gắn nhãn `MOCK` rõ ràng) và xem trước phiếu in.

### 10. Kết nối Meta Thật (Fanpage OAuth & Webhooks)
Xem hướng dẫn đầy đủ tại [`docs/META_INTEGRATION.md`](docs/META_INTEGRATION.md):
1. Tạo ứng dụng Business trên Meta for Developers, thêm sản phẩm **Facebook Login**, **Webhooks** và **Messenger**.
2. Điền `META_APP_ID`, `META_APP_SECRET`, `META_WEBHOOK_VERIFY_TOKEN` vào `.env`.
3. Cấu hình Webhook URL `https://<domain>/api/v1/webhooks/meta` (subscribe trường `feed` của `Page`).
4. Hoàn tất **Meta App Review** cho các quyền `pages_show_list`, `pages_read_engagement`, `pages_manage_metadata`, `pages_messaging`.

### 11. Triển khai Production (Deploy)
Xem hướng dẫn chi tiết kèm quy trình Backup/Restore tại [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md):
```bash
# Đặt APP_ENV=production và cấu hình secret thật trong .env
docker compose up -d --build
```

---

## Danh Mục Tài Liệu Kỹ Thuật (`docs/`)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): Kiến trúc tổng thể, sơ đồ luồng dữ liệu, thiết kế 16 bảng DB và cơ chế chống trùng đơn.
- [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md): Các giả định kỹ thuật và nghiệp vụ hợp lý.
- [`docs/META_INTEGRATION.md`](docs/META_INTEGRATION.md): Tài liệu xác minh API Meta chính thức, quyền hạn, giới hạn Private Replies 7 ngày và checklist App Review.
- [`docs/SETUP.md`](docs/SETUP.md): Hướng dẫn cài đặt môi trường phát triển.
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md): Hướng dẫn triển khai Production, sao lưu (Backup) và khôi phục (Restore).
- [`docs/TESTING.md`](docs/TESTING.md): Báo cáo và hướng dẫn chạy bộ kiểm thử `pytest`, `Vitest` và `Playwright`.
- [`docs/PRIVACY_AND_SECURITY.md`](docs/PRIVACY_AND_SECURITY.md): Chính sách bảo mật, mã hóa token và cô lập dữ liệu đa cửa hàng.
- [`docs/PRINTING.md`](docs/PRINTING.md): Hướng dẫn cấu hình và vận hành in phiếu chốt đơn (80mm, A6, A5).
- [`docs/ACCEPTANCE_CHECKLIST.md`](docs/ACCEPTANCE_CHECKLIST.md): Báo cáo nghiệm thu trung thực đối chiếu 20 tiêu chí.
