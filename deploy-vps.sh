#!/usr/bin/env bash
set -euo pipefail

echo "=================================================================="
echo "   CHOTLIVE - PRODUCTION VPS AUTO-INSTALLER (UBUNTU / DEBIAN)     "
echo "=================================================================="

if [ ! -f .env ]; then
  echo "[!] Chua tim thay file .env. Dang tao file .env tu mau .env.example..."
  cp .env.example .env
  echo "[!] Vui long mo file .env (nano .env) va dien DOMAIN, POSTGRES_PASSWORD, META_APP_ID, META_APP_SECRET truoc khi chay lai!"
  exit 1
fi

# 1. Cài đặt Docker & Docker Compose nếu VPS chưa có
if ! command -v docker &> /dev/null; then
  echo "[1/3] Dang cai dat Docker Engine tren VPS..."
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER" || true
fi

# 2. Tạo thư mục sao lưu dữ liệu tự động
mkdir -p backups

# 3. Khởi chạy toàn bộ hệ thống Production (Caddy HTTPS + Postgres 16 + Redis 7 + Backend + Frontend)
echo "[2/3] Dang build va khoi dong he thong ChotLive Production..."
sudo docker compose -f docker-compose.prod.yml up -d --build

echo "[3/3] Kiem tra suc khoe he thong..."
sleep 5
sudo docker compose -f docker-compose.prod.yml ps

echo "=================================================================="
echo " HOAN TAT! He thong ChotLive da chay 24/7 tren VPS voi HTTPS tu dong."
echo "=================================================================="
