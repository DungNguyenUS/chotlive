# BÁO CÁO & HƯỚNG DẪN KIỂM THỬ TOÀN DIỆN (TESTING GUIDE)

Hệ thống ChotLive được kiểm thử tự động ở cả 3 tầng: **Backend Integration/Unit Tests (pytest)**, **Frontend Component/Unit Tests (Vitest + React Testing Library)** và **End-to-End Browser Tests (Playwright)**.

---

## 1. Cách Chạy Các Bộ Kiểm Thử

### 1.1. Backend Tests (`pytest`)
```powershell
cd backend
.\.venv\Scripts\pytest.exe -v
```
**Kết quả thực tế đã xác minh**: `6 passed` bao gồm:
- `test_comment_parser_vietnamese_patterns`: Kiểm tra phân tích các mẫu câu chốt đơn tiếng Việt (`"Mã A50 chị Hằng chốt"`, `"Chốt 2 áo A50 màu đỏ size M"`, `"Cho em một cái mã B20"`, `"A50 lấy 3"`), phát hiện bình luận mơ hồ (nhiều mã hàng hoặc mã không có trong danh mục).
- `test_full_order_workflow_and_anti_duplicate_concurrency`: Kiểm tra luồng tạo shop, sản phẩm, phiên live, nhận bình luận, giữ nguyên `raw_message`, tính tiền chính xác, snapshot giá bất biến khi đổi bảng giá sau này, chống trùng đơn khi 2 nhân viên cùng bấm **ĐÃ CHỐT** trên một bình luận, hủy đơn và loại trừ đơn hủy khỏi doanh thu.
- `test_messenger_policies_retry_and_personal_profile_manual_mode`: Kiểm tra gửi thành công qua Mock, kiểm tra nguồn Trang Cá Nhân (`MANUAL_MODE` -> `NEEDS_MANUAL_ACTION`), lỗi `AMBIGUOUS_WRITE_TIMEOUT` không tự động gửi lại để tránh trùng, retry exponential backoff có giới hạn với lỗi tạm thời `503`, và chặn bình luận quá hạn 7 ngày theo chính sách Meta Private Replies.
- `test_printing_vietnamese_paper_sizes_and_bridge_failure_resilience`: Kiểm tra hiển thị tiếng Việt, bình luận dài, khổ giấy 80mm/A6/A5, in lại (reprint), và đảm bảo lỗi mất kết nối Local Print Bridge không bao giờ làm mất đơn hàng đã chốt.
- `test_security_cross_shop_isolation_webhook_signature_and_rate_limit`: Kiểm tra chặn truy cập chéo giữa 2 shop (`403 Forbidden`), chặn người dùng chưa đăng nhập (`401 Unauthorized`), chặn giá âm (`422`), xác minh chữ ký `X-Hub-Signature-256` của Meta Webhook, chống trùng lặp sự kiện Webhook và kiểm tra Rate Limiting (`429 Too Many Requests`).
- `test_csv_import_export_and_staff_role_permissions`: Kiểm tra phân quyền `STAFF` không được phép sửa cấu hình shop hoặc thêm quản trị viên (`403 Forbidden`), kiểm tra nhập/xuất file CSV sản phẩm và lọc dòng dữ liệu không hợp lệ.

### 1.2. Frontend Unit Tests (`Vitest`)
```powershell
cd frontend
npm test
```
**Kết quả thực tế đã xác minh**: `4 passed` (`src/__tests__/app.test.tsx`), kiểm tra định dạng tiền tệ VNĐ, phân biệt rõ các badge trạng thái (`DEMO`, `CONNECTED`, `MANUAL_MODE`, `NEEDS_PERMISSION`, `FAILED`), màn hình đăng nhập, báo lỗi xác thực và banner cảnh báo mất kết nối.

### 1.3. End-to-End Tests (`Playwright`)
Khi Backend (`:8000`) và Frontend (`:3000`) đang chạy:
```powershell
cd frontend
npx playwright test
```
**Kết quả thực tế đã xác minh**: `1 passed` (`e2e/chotlive.spec.ts`), chạy trình duyệt thực tế qua toàn bộ hành trình: Đăng nhập -> Chọn Shop -> Tạo sản phẩm mới -> Nhập bình luận livestream -> Bấm nút **ĐÃ CHỐT** -> Kiểm tra nội dung tiếng Việt và thành tiền trên hộp thoại Xem trước phiếu in -> Xác nhận đã in -> Kiểm tra trạng thái tin nhắn trong lịch sử Messenger.
