$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   KHOI DONG HE THONG DEMO CHOTLIVE (BACKEND + FRONTEND)  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Giải phóng cổng 8000 và 3000 nếu đang có tiến trình cũ chạy ngầm
Get-NetTCPConnection -LocalPort 8000,3000 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}

# 1. Chạy Migration & Seed dữ liệu mẫu trong Backend
Set-Location "$PSScriptRoot\backend"
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m app.seed

# 2. Mở cửa sổ chạy Backend (cổng 8000)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\backend'; .\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload"

# 3. Mở cửa sổ chạy Frontend (cổng 3000)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\frontend'; npm run dev"

Write-Host ""
Write-Host "Da khoi dong thanh cong 2 cua so Backend (:8000) va Frontend (:3000)!" -ForegroundColor Green
Write-Host "-> Truy cap Web App tai: http://localhost:3000" -ForegroundColor Yellow
Write-Host "-> Tai khoan Demo:       owner@chotlive.vn / ChotLive@2026" -ForegroundColor Yellow
