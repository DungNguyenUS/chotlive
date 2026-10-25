# HƯỚNG DẪN TRIỂN KHAI PRODUCTION, BACKUP & KHÔI PHỤC DỮ LIỆU (DEPLOYMENT & BACKUP)

## 1. Chuẩn Bị Triển Khai Production

1. **Thiết lập biến môi trường `.env` trên máy chủ Production**:
   - Đặt `APP_ENV=production` (bắt buộc để khóa hoàn toàn Mock Provider và ẩn trang `/docs` debug).
   - Đặt `DATABASE_URL=postgresql+psycopg://<user>:<password>@postgres:5432/chotlive_db`.
   - Sinh `SECRET_KEY` ngẫu nhiên tối thiểu 32 ký tự:
     ```bash
     python -c "import secrets; print(secrets.token_urlsafe(48))"
     ```
   - Sinh `ENCRYPTION_KEY` chuẩn Fernet 32-byte base64 để mã hóa Page Access Token:
     ```bash
     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
     ```
   - Cung cấp `META_APP_ID`, `META_APP_SECRET`, `META_WEBHOOK_VERIFY_TOKEN` thật từ Meta for Developers.

2. **Cấu hình HTTPS & Reverse Proxy (Nginx / Caddy / Cloudflare)**:
   - Meta Webhooks và Facebook Login OAuth **bắt buộc** sử dụng giao thức `HTTPS` với chứng chỉ SSL hợp lệ.
   - Trỏ domain `https://live.ten-shop-cua-ban.vn/api/v1/webhooks/meta` vào cổng `8000` của dịch vụ `backend`.

3. **Khởi chạy Production với Docker Compose**:
   ```bash
   docker compose up -d --build
   ```

---

## 2. Quy Trình Sao Lưu (Backup) Cơ Sở Dữ Liệu

### 2.1. Sao lưu PostgreSQL (Production / Docker)
Chạy lệnh `pg_dump` định kỳ (khuyến nghị mỗi 6 giờ qua cronjob và trước mọi lần chạy migration):
```bash
docker exec -t chotlive-postgres pg_dump -U chotlive_user -d chotlive_db -F c -f /tmp/chotlive_backup_$(date +%Y%m%d_%H%M%S).dump
docker cp chotlive-postgres:/tmp/chotlive_backup_*.dump ./backups/
```

### 2.2. Sao lưu SQLite (Local Development)
```powershell
Copy-Item backend/chotlive_dev.db backups/chotlive_dev_$(Get-Date -Format "yyyyMMdd_HHmmss").db
```

---

## 3. Quy Trình Khôi Phục (Restore) Cơ Sở Dữ Liệu

### 3.1. Khôi phục PostgreSQL từ file dump
```bash
docker cp ./backups/chotlive_backup_YYYYMMDD_HHMMSS.dump chotlive-postgres:/tmp/restore.dump
docker exec -i chotlive-postgres pg_restore -U chotlive_user -d chotlive_db --clean --if-exists /tmp/restore.dump
```

### 3.2. Kiểm tra tính toàn vẹn sau khi khôi phục
```bash
curl -f http://localhost:8000/api/v1/health
```
