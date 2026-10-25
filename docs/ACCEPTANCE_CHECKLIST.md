# BÁO CÁO NGHIỆM THU HỆ THỐNG CHOTLIVE (ACCEPTANCE CHECKLIST)

Báo cáo này đối chiếu từng tiêu chí trong 20 tiêu chí nghiệm thu bắt buộc với kết quả kiểm thử thực tế trên môi trường hiện tại.

---

## Bảng Kết Quả Nghiệm Thu Chi Tiết

| STT | Tiêu chí nghiệm thu | Trạng thái | Bằng chứng kiểm chứng thực tế |
| :---: | :--- | :---: | :--- |
| 1 | Project khởi động theo README trên môi trường sạch | **PASS** | Backend (`uvicorn` cổng 8000) trả về `/api/v1/health` `status: healthy`; Frontend (`next build` & `next start` cổng 3000) khởi chạy thành công. |
| 2 | Database migrations chạy được | **PASS** | Đã chạy `alembic revision --autogenerate` và `alembic upgrade head` khởi tạo sạch toàn bộ 16 bảng, khóa ngoại, unique constraints và indexes (`43c8beb627b6_initial_schema_16_tables.py`). |
| 3 | User đăng nhập và tạo shop được | **PASS** | Đã kiểm chứng qua `pytest` (`test_full_order_workflow...`) và trình duyệt `Playwright` (`e2e/chotlive.spec.ts`). |
| 4 | Shop tạo, sửa, tìm kiếm, nhập/xuất CSV sản phẩm được | **PASS** | Đã kiểm chứng qua `test_full_order_workflow...`, `test_csv_import_export...` và `e2e/chotlive.spec.ts`. |
| 5 | Mock livestream đưa comment vào dashboard | **PASS** | Đã kiểm chứng qua `app.seed`, API `/shops/{id}/comments`, Webhook `/webhooks/meta` và E2E test. |
| 6 | Tìm kiếm và lọc comment hoạt động | **PASS** | Hỗ trợ tìm theo tên khách, mã hàng, nội dung bình luận; lọc theo nguồn (`FACEBOOK_PAGE`, `FACEBOOK_PERSONAL`, `DEMO`), phiên live, trạng thái và sắp xếp ưu tiên khách bình luận trước (`sort=asc`). |
| 7 | Chốt comment tạo đơn đúng một lần | **PASS** | Quy trình 13 bước trong `confirm_order_from_comment` tạo đúng 1 `Order` + `OrderItem` snapshot + `AuditLog`. |
| 8 | Nhiều request đồng thời không tạo đơn trùng ngoài chủ đích | **PASS** | Kết hợp `UNIQUE(shop_id, comment_id)`, `UNIQUE(shop_id, idempotency_key)` ở tầng DB và xử lý `IntegrityError` idempotent replay. Đã kiểm chứng trong `test_full_order_workflow_and_anti_duplicate_concurrency`. |
| 9 | Giá và số lượng được tính đúng (snapshot giá bất biến) | **PASS** | Giá lấy từ bảng giá hiện hành của shop; lưu `unit_price_snapshot` trong `order_items`. Đã kiểm chứng khi đổi giá sản phẩm sau đó đơn cũ không bị thay đổi. |
| 10 | Thông tin gốc của comment được giữ nguyên | **PASS** | Trường `raw_message` được lưu nguyên vẹn 100% và hiển thị nguyên gốc trên giao diện cũng như trên phiếu in. |
| 11 | Tin nhắn mock có nội dung đúng và trạng thái minh bạch | **PASS** | `provider_mode="MOCK"` hoặc `"MANUAL"`, render đúng mẫu tiếng Việt của shop, kiểm tra giới hạn 7 ngày, retry exponential backoff có giới hạn và `NEEDS_MANUAL_ACTION`. |
| 12 | Real Messenger integration được đánh dấu **BLOCKED** cho tới khi API, quyền và credentials thực sự hoạt động | **BLOCKED** (Đúng quy định) | Endpoint `/api/v1/meta/integration-status`, `/api/v1/health` và `RealMetaGraphMessengerAdapter` đánh dấu rõ `BLOCKED_MISSING_CREDENTIALS` cho tới khi người dùng cung cấp `META_APP_ID`, `META_APP_SECRET`, Page Access Token thật và hoàn tất Meta App Review (`pages_messaging`). |
| 13 | Phiếu in hiển thị tiếng Việt và đủ trường (80mm / A6 / A5) | **PASS** | Đã kiểm chứng qua `test_printing_vietnamese_paper_sizes...` và Playwright E2E test (`PHIẾU CHỐT ĐƠN LIVESTREAM`, STT tách biệt mã đơn, ngày giờ, tên khách, bình luận gốc, sản phẩm, thành tiền). |
| 14 | Lỗi in không làm mất đơn | **PASS** | Đã kiểm chứng trong `test_printing_vietnamese_paper_sizes_and_bridge_failure_resilience`: khi Local Print Bridge lỗi kết nối, `PrintJob.status = FAILED` nhưng `Order.status = CONFIRMED` vẫn được bảo toàn nguyên vẹn. |
| 15 | Quyền truy cập được kiểm tra phía server | **PASS** | Kiểm tra JWT (`401`) và phân quyền vai trò `OWNER`/`ADMIN`/`STAFF` (`403`) trực tiếp tại tầng FastAPI dependency `get_shop_access`. |
| 16 | Dữ liệu các shop không bị truy cập chéo | **PASS** | Đã kiểm chứng trong `test_security_cross_shop_isolation...`: Chủ Shop B truy cập dữ liệu của Shop A nhận mã lỗi `403 Forbidden`. |
| 17 | Test suite chạy và kết quả được ghi lại | **PASS** | Backend `pytest`: **6 passed**; Frontend `vitest`: **4 passed**; End-to-End `Playwright`: **1 passed**. |
| 18 | Không có secret thật trong repository | **PASS** | Đã kiểm tra `.env.example` và toàn bộ mã nguồn chỉ chứa biến mẫu an toàn; file `.env` và `*.db` đã được đưa vào `.gitignore`. |
| 19 | Có hướng dẫn backup và restore | **PASS** | Đã tài liệu hóa chi tiết trong `docs/DEPLOYMENT.md` cho cả PostgreSQL (`pg_dump`/`pg_restore`) và SQLite. |
| 20 | Có checklist kết nối Facebook thật và triển khai production | **PASS** | Đã tài liệu hóa đầy đủ trong `docs/META_INTEGRATION.md`, `docs/DEPLOYMENT.md` và `README.md`. |

---

## Các Hạng Mục Phụ Thuộc Người Dùng / Bên Thứ Ba Để Lên Production Thật

1. **Meta App Credentials & App Review (Blocker bên ngoài cho Real Messenger/Page API)**:
   - Cung cấp `META_APP_ID`, `META_APP_SECRET`, `META_WEBHOOK_VERIFY_TOKEN` từ tài khoản Meta for Developers của doanh nghiệp.
   - Xin cấp quyền **Advanced Access** cho `pages_show_list`, `pages_read_engagement`, `pages_manage_metadata`, `pages_messaging`.
2. **Dịch Vụ Docker / PostgreSQL / HTTPS Domain trên Server Production**:
   - Bật Docker daemon trên máy chủ triển khai và cấu hình tên miền HTTPS công khai để nhận Webhook trực tiếp từ Meta.
3. **Máy In Nhiệt Vật Lý (Nếu dùng chế độ Local Print Bridge)**:
   - Kết nối máy in nhiệt K80 (80mm) và trỏ `PRINT_BRIDGE_URL` tới dịch vụ in nội bộ tại cửa hàng (hoặc sử dụng ngay chế độ **Browser Print** có sẵn không cần cài đặt thêm).
