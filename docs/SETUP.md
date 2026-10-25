# HƯỚNG DẪN CÀI ĐẶT & KHỞI ĐỘNG HỆ THỐNG (SETUP GUIDE)

## 1. Yêu Cầu Môi Trường
- **Python**: 3.9+ (khuyến nghị 3.12 trong Docker/Production)
- **Node.js**: 18+ hoặc 20+
- **Database**: PostgreSQL 16 (hoặc SQLite WAL tự động cho môi trường phát triển cục bộ khi chưa bật Docker)
- **Redis**: Redis 7 (tùy chọn cho môi trường phát triển cục bộ)

## 2. Cài Đặt Nhanh Trên Môi Trường Phát Triển (Local Development)

### Bước 1: Sao chép file cấu hình môi trường
```powershell
Copy-Item .env.example .env
```

### Bước 2: Cài đặt Backend & Chạy Migrations
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m app.seed
```

### Bước 3: Khởi động Backend API (Cổng 8000)
```powershell
cd backend
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```
- Tài liệu OpenAPI (Swagger): `http://localhost:8000/docs`
- Healthcheck: `http://localhost:8000/api/v1/health`

### Bước 4: Cài đặt & Khởi động Frontend (Cổng 3000)
```powershell
cd frontend
npm install
npm run dev
```
- Truy cập ứng dụng tại: `http://localhost:3000`
- Tài khoản mẫu Development (được tạo bởi `app.seed`):
  - Chủ shop (`OWNER`): `owner@chotlive.vn` / `ChotLive@2026`
  - Nhân viên (`STAFF`): `staff@chotlive.vn` / `ChotLive@2026`

## 3. Khởi Động Bằng Docker Compose (PostgreSQL + Redis + Backend + Frontend)
Khi dịch vụ Docker Desktop đã được bật:
```powershell
docker compose up -d --build
```
