# GIẢ ĐỊNH KỸ THUẬT VÀ NGHIỆP VỤ (ASSUMPTIONS)

Tài liệu này ghi lại đầy đủ các giả định hợp lý được đưa ra trong quá trình thiết kế và xây dựng hệ thống ChotLive để đảm bảo hệ thống chạy ổn định, an toàn, có thể kiểm thử tự động ngay trên môi trường hiện tại mà không vi phạm chính sách của Meta.

---

## 1. Môi Trường Thực Thi & Cơ Sở Dữ Liệu

1. **PostgreSQL & SQLite Fallback cho Môi Trường Local**:
   - Trong môi trường Production và Docker Compose, hệ thống sử dụng **PostgreSQL 16** và **Redis 7** theo đúng kiến trúc chuẩn (`DATABASE_URL=postgresql+psycopg://...`).
   - Trên máy phát triển hiện tại, dịch vụ Windows `com.docker.service` đang ở trạng thái `Stopped` và không có PostgreSQL/Redis daemon chạy nền trực tiếp trên host.
   - **Giải pháp kỹ thuật**: Hệ thống cấu hình SQLAlchemy 2.x và Alembic tương thích hoàn toàn với cả PostgreSQL và SQLite (chế độ WAL + Foreign Keys `ON` + Unique Constraints đầy đủ). Khi chạy ở `APP_ENV=development` hoặc `APP_ENV=test` mà chưa bật Docker, ứng dụng tự động cho phép sử dụng `sqlite:///./chotlive_dev.db` và hàng đợi tác vụ đồng bộ/in-memory an toàn để toàn bộ Migration, Backend, Frontend, Unit Tests, Integration Tests và E2E Tests đều chạy và kiểm chứng thật 100%. Khi triển khai lên Docker hoặc máy chủ có PostgreSQL, chỉ cần đổi `DATABASE_URL` sang PostgreSQL mà không cần sửa code.

2. **Chế Độ Mock Provider Trong Development vs Production**:
   - Ở môi trường `development` hoặc `test`, khi chưa cấu hình `META_APP_ID` và `META_APP_SECRET` thật, hệ thống kích hoạt `MockMetaAdapter` một cách **tường minh**, gắn nhãn rõ ràng là `DEMO` hoặc `MANUAL_MODE` trên mọi giao diện và bản ghi.
   - Ở môi trường `production` (`APP_ENV=production`), hệ thống **cấm tuyệt đối** việc tự động fallback sang Mock Provider. Nếu thiếu thông tin xác thực Meta khi gọi tính năng Meta thật, hệ thống báo trạng thái `MISSING_CREDENTIALS` / `BLOCKED` minh bạch.

---

## 2. Nghiệp Vụ Livestream & Chính Sách Meta

1. **Nguồn Livestream Trang Cá Nhân (Facebook Personal Profile)**:
   - Meta Graph API chính thức **không hỗ trợ** đọc bình luận livestream tự động bằng Webhook hoặc gửi Private Replies cho tài khoản Facebook cá nhân thông thường (trừ khi chuyển sang chế độ Professional Mode và đáp ứng điều kiện Page-backed API của Meta).
   - Tuân thủ nghiêm ngặt quy tắc không dùng scraping, không lưu mật khẩu Facebook, không giả lập trình duyệt trái phép: Đối với nguồn **Facebook Trang Cá Nhân**, hệ thống đặt trạng thái kết nối là `MANUAL_MODE` và cung cấp công cụ:
     - Nhập nhanh bình luận thủ công (Single Quick Entry) hoặc dán hàng loạt (Batch Paste từ livestream).
     - Khi chốt đơn từ nguồn trang cá nhân, trạng thái tin nhắn Messenger được chuyển thẳng sang `NEEDS_MANUAL_ACTION`, kèm theo bản xem trước tin nhắn đã điền sẵn thông tin đơn, nút **Sao chép nội dung** và nút **Mở Messenger** (nếu có link/UID hợp lệ), tuyệt đối không báo "Đã gửi thành công" khi nhân viên chỉ mới sao chép hoặc bấm mở link.

2. **Quy Tắc Gửi Tin Nhắn Messenger (Private Replies API)**:
   - Chỉ áp dụng cho nguồn `FACEBOOK_PAGE` có kết nối `CONNECTED` và có quyền `pages_messaging` + `pages_read_engagement`.
   - Điều kiện gửi hợp lệ:
     - Bình luận có `external_comment_id` từ nền tảng Meta.
     - Thời gian bình luận chưa quá **7 ngày** tính tới thời điểm gửi.
     - Bình luận đó chưa từng được gửi Private Reply thành công trước đó (Meta chỉ cho phép gửi tối đa **1 tin nhắn Private Reply** cho mỗi `comment_id`).
   - Nếu gặp lỗi mạng hoặc HTTP 5xx / Rate Limit tạm thời, hệ thống mới thực hiện retry theo thuật toán Exponential Backoff (tối đa 3 lần). Nếu không xác định được trạng thái phản hồi trước đó (ví dụ timeout sau khi gửi payload mà không rõ Meta đã nhận hay chưa), hệ thống chuyển sang `NEEDS_MANUAL_ACTION` để tránh gửi lặp hoặc thông báo sai.

3. **Bộ Phân Tích Bình Luận (Comment Parser)**:
   - Các shop Việt Nam thường đặt mã sản phẩm ngắn gọn dạng chữ cái kết hợp chữ số (ví dụ: `A50`, `B20`, `V12`, `SET01`, `D105`).
   - Hỗ trợ từ khóa ý định mua phổ biến: `chốt`, `lấy`, `cho em`, `cho chị`, `đặt`, `mua`, `ok mã`, hoặc cú pháp rút gọn `<Mã SP> <Số lượng>` (ví dụ `A50 lấy 3`, `2 cái A50`).
   - Hỗ trợ đọc số lượng bằng chữ tiếng Việt (`một`, `hai`, `ba`, `bốn`, `năm`, `sáu`, `bảy`, `tám`, `chín`, `mười`, `chục`, `đôi`, `cặp`).
   - Nếu trong một bình luận xuất hiện nhiều mã sản phẩm khác nhau hoặc mã sản phẩm không tồn tại trong danh mục đang hoạt động của shop, hệ thống đánh dấu `is_ambiguous = True` và yêu cầu nhân viên xác nhận rõ ràng trước khi tạo đơn.

4. **Số Thứ Tự Khách Hàng (STT) và Mã Đơn Hàng (`order_code`)**:
   - `customer_stt` (ví dụ: `#01`, `#02`, `#15`) là số thứ tự dễ đọc dùng để gọi tên trên livestream và in to trên đầu phiếu in. Shop có thể cấu hình quy tắc reset STT: theo ngày (`DAILY`), theo phiên live (`SESSION`) hoặc không tự reset (`NEVER`).
   - `order_code` (ví dụ: `DH-20261024-0001`) là mã định danh duy nhất của từng đơn hàng trong phạm vi shop. Một khách hàng chốt 3 bình luận khác nhau trong cùng phiên live có thể giữ cùng số STT khách hàng trong phiên đó (hoặc theo cấu hình shop) nhưng luôn có 3 `order_code` riêng biệt.

5. **In Phiếu Chốt Đơn**:
   - Việc mở hộp thoại in của trình duyệt (`window.print()`) không cho phép JavaScript biết chắc chắn máy in vật lý đã nạp giấy và in xong hay người dùng bấm Cancel. Vì vậy, sau khi mở hộp thoại in trình duyệt, trạng thái job là `PRINTING` và hiển thị nút để nhân viên xác nhận **"Đã in xong"** (`PRINTED`) hoặc **"Báo lỗi in"** (`FAILED`), đảm bảo không giả mạo trạng thái thành công.
   - Với chế độ `PRINT_BRIDGE`, hệ thống gửi lệnh qua HTTP tới dịch vụ Local Print Bridge (`PRINT_BRIDGE_URL`) và chỉ đánh dấu `PRINTED` khi nhận được phản hồi xác nhận từ bridge.
