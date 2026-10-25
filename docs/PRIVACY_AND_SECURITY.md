# CHÍNH SÁCH BẢO MẬT, QUYỀN RIÊNG TƯ & TUÂN THỦ META (PRIVACY & SECURITY)

## 1. Các Biện Pháp Bảo Mật Đã Triển Khai

1. **Xác Thực & Mật Khẩu**:
   - Mật khẩu người dùng hệ thống ChotLive được băm bằng thuật toán `bcrypt` (12 rounds).
   - Hệ thống **tuyệt đối không bao giờ** yêu cầu hoặc lưu trữ mật khẩu tài khoản Facebook của người dùng.
2. **Bảo Vệ Token Của Meta (`encrypted_access_token`)**:
   - Page Access Token được mã hóa đối xứng bằng `Fernet` (AES-128-CBC + HMAC-SHA256) thông qua `ENCRYPTION_KEY` trước khi lưu xuống cơ sở dữ liệu.
   - Không ghi Access Token, mật khẩu hoặc secret vào console/file log.
3. **Cô Lập Dữ Liệu Đa Cửa Hàng (Shop-Level Multi-Tenancy Isolation)**:
   - Tất cả 16 bảng dữ liệu nghiệp vụ đều gắn khóa ngoại `shop_id`.
   - Mọi API endpoint `/api/v1/shops/{shop_id}/...` đều kiểm tra quyền thành viên tại tầng Backend (`get_shop_access`), đồng thời kiểm tra vai trò (`OWNER`, `ADMIN`, `STAFF`) trước khi thực hiện thao tác nhạy cảm.
4. **Xác Thực Webhook Meta (`X-Hub-Signature-256`)**:
   - Mọi gói tin gửi đến `/api/v1/webhooks/meta` đều được kiểm tra chữ ký `HMAC-SHA256` bằng `META_APP_SECRET` với `hmac.compare_digest` chống tấn công timing attack.
5. **Chống SQL Injection, XSS & Giới Hạn Tần Suất (Rate Limiting)**:
   - Sử dụng 100% truy vấn tham số hóa qua SQLAlchemy 2.x ORM.
   - Toàn bộ dữ liệu xuất ra mẫu phiếu in HTML đều được escape qua `html.escape()`.
   - Tích hợp bộ giới hạn tần suất (Rate Limiter) trả về `429 Too Many Requests` khi vượt ngưỡng cấu hình.

## 2. Chính Sách Lưu Trữ & Xóa Dữ Liệu Cá Nhân (Data Retention & Deletion)

- **Nguyên tắc tối thiểu hóa dữ liệu**: Hệ thống chỉ lưu trữ tên hiển thị, ID người bình luận do nền tảng cung cấp, nội dung bình luận đặt hàng và thông tin giao nhận do khách hàng cung cấp cho shop.
- **Xóa dữ liệu theo yêu cầu**: Chủ shop (`OWNER`) hoặc quản trị viên hệ thống có thể xóa toàn bộ dữ liệu cửa hàng hoặc thông tin khách hàng khi có yêu cầu xóa dữ liệu từ người dùng theo chính sách nền tảng của Meta (`Data Deletion Request Callback`).
