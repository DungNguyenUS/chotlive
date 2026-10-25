# TÀI LIỆU TÍCH HỢP META CHÍNH THỨC (META GRAPH API & MESSENGER PLATFORM)

Tài liệu này ghi rõ các tài liệu chính thức của Meta for Developers, phiên bản API, quyền hạn (Permissions), điều kiện truy cập, giới hạn chính sách và trạng thái kiểm thử cho từng tính năng tích hợp trong hệ thống ChotLive.

---

## 1. Bảng Tổng Hợp Các Tính Năng Tích Hợp Meta

| Tính năng | Tài liệu chính thức Meta | API Version | Endpoint chính | Quyền bắt buộc (Permissions) | Điều kiện truy cập | Trạng thái kiểm thử hiện tại |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Đăng nhập & Ủy quyền Fanpage (Meta OAuth)** | `https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow` | `v21.0` | `GET /dialog/oauth`<br>`GET /oauth/access_token`<br>`GET /me/accounts` | `pages_show_list`<br>`pages_read_engagement`<br>`pages_manage_metadata`<br>`pages_messaging` | Quản trị viên của Fanpage thực hiện OAuth; cần **Advanced Access** qua App Review cho người dùng ngoài App Roles | **Mock Tested** (100% Automated)<br>**Real API: BLOCKED** (Chờ người dùng cung cấp `META_APP_ID`, `META_APP_SECRET` và hoàn tất App Review) |
| **2. Nhận bình luận Livestream qua Webhooks** | `https://developers.facebook.com/docs/graph-api/webhooks/reference/page/#feed` | `v21.0` | `POST /{page-id}/subscribed_apps` (field: `feed`, item: `comment`, verb: `add`) | `pages_read_engagement`<br>`pages_manage_metadata` | App phải đăng ký Webhook `page` -> `feed`, xác minh `hub.verify_token` và chữ ký `X-Hub-Signature-256` | **Mock & Signature Tested** (100% Automated)<br>**Real Webhook: BLOCKED** (Chờ public HTTPS URL & Meta App) |
| **3. Đọc bình luận Livestream qua Polling (Live Video API)** | `https://developers.facebook.com/docs/live-video-api/guides/Reading-Comments/` | `v21.0` | `GET /{live-video-id}/comments?order=reverse_chronological&filter=stream` | `pages_read_engagement`<br>`pages_show_list` | Sử dụng **Page Access Token** của Fanpage đang phát trực tiếp | **Mock Tested** (100% Automated)<br>**Real API: BLOCKED** (Chờ Page Access Token thật) |
| **4. Gửi tin nhắn Private Replies qua Messenger** | `https://developers.facebook.com/docs/messenger-platform/discovery/private-replies/` | `v21.0` | `POST /{page-id}/messages`<br>Body: `{"recipient": {"comment_id": "..."}, "message": {"text": "..."}}` | `pages_messaging`<br>`pages_read_engagement` | - Chỉ gửi được cho bình luận trên Page/Live<br>- Trong vòng **7 ngày** kể từ lúc bình luận<br>- Tối đa **1 tin nhắn Private Reply** cho mỗi `comment_id` | **Mock & Policy Tested** (100% Automated)<br>**Real API: BLOCKED** (Chờ `pages_messaging` Advanced Access & Page Token) |
| **5. Livestream trên Facebook Trang Cá Nhân** | `https://developers.facebook.com/docs/live-video-api/` | N/A | Không có API mở cho tài khoản cá nhân tiêu chuẩn | N/A | Meta không cấp quyền đọc comment livestream hoặc gửi Private Reply tự động cho tài khoản cá nhân tiêu chuẩn (trừ khi dùng Page/Professional Mode đủ điều kiện) | **Supported via `MANUAL_MODE`** (Nhập thủ công hợp pháp & hỗ trợ sao chép/mở Messenger, tuyệt đối không dùng scraping) |

---

## 2. Chi Tiết Chính Sách & Giới Hạn Kỹ Thuật Bắt Buộc Tuân Thủ

### 2.1. Xác Minh Chữ Ký Webhook (`X-Hub-Signature-256`)
- Tài liệu: `https://developers.facebook.com/docs/graph-api/webhooks/getting-started#verification-requests`
- Khi Meta đăng ký Webhook (`GET /api/v1/webhooks/meta`), hệ thống kiểm tra `hub.mode == "subscribe"` và đối chiếu `hub.verify_token` với biến môi trường `META_WEBHOOK_VERIFY_TOKEN` bằng phép so sánh an toàn (`hmac.compare_digest`).
- Khi Meta gửi sự kiện (`POST /api/v1/webhooks/meta`), hệ thống đọc raw body và tính `HMAC-SHA256` với khóa là `META_APP_SECRET`. Nếu header `X-Hub-Signature-256` không khớp, trả về `403 Forbidden` ngay lập tức.

### 2.2. Chính Sách Private Replies (Messenger Platform)
- Tài liệu: `https://developers.facebook.com/docs/messenger-platform/discovery/private-replies/`
- **Quy tắc 1 phản hồi duy nhất**: Mỗi bình luận (`comment_id`) chỉ được nhận đúng 1 tin nhắn phản hồi riêng tư từ Fanpage. Cuộc hội thoại 24 giờ chỉ mở ra khi khách hàng chủ động trả lời lại tin nhắn đó.
- **Giới hạn thời gian 7 ngày**: Không thể gửi Private Reply cho bình luận đã tạo quá 7 ngày (168 giờ). Hệ thống kiểm tra tuổi của bình luận trước khi gọi API; nếu quá 7 ngày sẽ chuyển sang trạng thái `NEEDS_MANUAL_ACTION` với lý do rõ ràng.
- **Rate Limits**:
  - Mặc định: 750 lệnh gọi / giờ / Fanpage.
  - Fanpage có gắn Shop hoặc có video Live đạt $\ge 2.000$ bình luận trong 28 ngày gần nhất: tới 30.000 lệnh gọi / giờ.
- **Cơ chế Retry và Tránh Gửi Trùng**:
  - Chỉ retry (với Exponential Backoff) cho các lỗi mạng tạm thời hoặc HTTP 500/502/503/504 và mã lỗi tạm thời.
  - Không bao giờ retry nếu lỗi là thiếu quyền (`#10`, `#200`), bình luận đã được phản hồi trước đó (`#10900`), hoặc bình luận quá hạn.
  - Nếu xảy ra lỗi không xác định được liệu Meta đã gửi tin nhắn đi hay chưa (ambiguous write timeout), hệ thống dừng retry và đặt trạng thái `NEEDS_MANUAL_ACTION` để nhân viên kiểm tra, tuyệt đối không mạo hiểm gửi trùng.

### 2.3. Bảo Mật Access Token
- Page Access Token thu được qua luồng OAuth không bao giờ được lưu dạng văn bản thuần (plaintext) trong cơ sở dữ liệu hay ghi ra log.
- Hệ thống mã hóa đối xứng bằng `Fernet` (`cryptography.fernet`) sử dụng `ENCRYPTION_KEY` trước khi lưu vào cột `encrypted_access_token` của bảng `connected_accounts`.

---

## 3. Phân Biệt Rõ Ràng Các Trạng Thái Kết Nối Nguồn (`connection_status`)

Hệ thống sử dụng enum trạng thái minh bạch, không bao giờ giả mạo trạng thái kết nối:
1. `DEMO`: Chế độ mô phỏng dành riêng cho môi trường phát triển/kiểm thử (tuyệt đối bị chặn tự động ở `APP_ENV=production`).
2. `CONNECTED`: Đã xác thực OAuth thành công với Meta, có Page Access Token còn hạn và đủ các quyền bắt buộc (`pages_show_list`, `pages_read_engagement`, `pages_messaging`).
3. `NEEDS_PERMISSION`: Đã kết nối tài khoản nhưng người dùng bỏ chọn một hoặc nhiều quyền quan trọng (ví dụ thiếu `pages_messaging` để gửi tin nhắn tự động). Hệ thống liệt kê chính xác danh sách `missing_permissions`.
4. `MANUAL_MODE`: Áp dụng cho nguồn Facebook Trang Cá Nhân hoặc khi chủ shop chủ động chọn chế độ nhập bình luận & gửi tin nhắn thủ công.
5. `FAILED`: Token hết hạn, bị thu hồi hoặc lỗi kết nối API của Meta.
6. `MISSING_CREDENTIALS`: Môi trường chưa cấu hình `META_APP_ID` / `META_APP_SECRET`.

---

## 4. Checklist Chuẩn Bị App Review & Kết Nối Meta Thật Cho Production

Để chuyển các tính năng từ trạng thái **Mock Tested** sang **Real Production Connected**, chủ hệ thống cần thực hiện:
1. Truy cập [Meta for Developers](https://developers.facebook.com/apps/) và tạo ứng dụng loại **Business**.
2. Thêm sản phẩm **Facebook Login for Business**, **Webhooks** và **Messenger**.
3. Điền `META_APP_ID`, `META_APP_SECRET`, `META_WEBHOOK_VERIFY_TOKEN` vào file `.env` trên máy chủ Production (chạy HTTPS).
4. Cấu hình **Valid OAuth Redirect URIs**: `https://<domain-cua-ban>/api/v1/meta/oauth/callback`.
5. Cấu hình **Webhook Callback URL** cho đối tượng `Page`: `https://<domain-cua-ban>/api/v1/webhooks/meta` và subscribe trường `feed`.
6. Chuẩn bị hồ sơ **Meta App Review** để xin quyền **Advanced Access** cho:
   - `pages_show_list`: Để liệt kê danh sách Fanpage của chủ shop.
   - `pages_read_engagement`: Để đọc bình luận trực tiếp từ phiên Livestream của Fanpage.
   - `pages_manage_metadata`: Để đăng ký nhận sự kiện Webhook từ Fanpage.
   - `pages_messaging`: Để gửi tin nhắn xác nhận đơn hàng tự động qua Private Replies API khi khách bình luận chốt đơn.
7. Quay video màn hình (Screencast) theo kịch bản có sẵn trên giao diện ChotLive để đính kèm vào hồ sơ App Review.
