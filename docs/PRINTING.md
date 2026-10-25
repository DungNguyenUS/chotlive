# HƯỚNG DẪN IN PHIẾU CHỐT ĐƠN LIVESTREAM (PRINTING GUIDE)

Hệ thống ChotLive hỗ trợ in phiếu chốt đơn tiếng Việt sắc nét trên 3 khổ giấy tiêu chuẩn (**80mm K80**, **A6**, **A5**) với hai chế độ vận hành minh bạch.

---

## 1. Nội Dung Chuẩn Trên Phiếu Chốt Đơn

Mỗi phiếu in đều lưu **Snapshot dữ liệu** tại thời điểm tạo đơn (đảm bảo khi in lại sau nhiều tháng, giá bán và thông tin vẫn giữ nguyên 100%):
- Tên Shop, SĐT, Logo (nếu có).
- Tiêu đề: **PHIẾU CHỐT ĐƠN LIVESTREAM**.
- **Số thứ tự khách hàng (STT)** đóng khung lớn (tách biệt hoàn toàn với Mã đơn hàng).
- Ngày, tháng, năm và giờ chốt đơn.
- Tên khách hàng & Nội dung bình luận nguyên gốc.
- Mã đơn hàng (`DH-YYYYMMDD-XXXX`).
- Mã sản phẩm, Tên sản phẩm, Biến thể (Màu/Size), Số lượng, Đơn giá, Thành tiền và Ghi chú.

---

## 2. Hai Chế Độ In Ấn

### Chế độ A: Browser Print (In trực tiếp qua trình duyệt)
- Sử dụng CSS `@page` tối ưu riêng cho từng khổ giấy (`80mm`, `105mm` cho A6, `148mm` cho A5).
- **Quy tắc trung thực trạng thái**:
  - Trình duyệt web không cung cấp API cho biết máy in vật lý đã nạp giấy và in xong hay người dùng bấm Hủy hộp thoại in.
  - Vì vậy, khi bấm **"Mở Hộp Thoại In Trình Duyệt"**, hệ thống chỉ chuyển trạng thái lệnh in sang `PRINTING`.
  - Chỉ khi nhân viên xác nhận phiếu đã ra khỏi máy in và bấm **"✓ Xác Nhận Đã In Xong"**, trạng thái mới chuyển thành `PRINTED`.

### Chế độ B: Local Print Bridge (In qua dịch vụ cầu nối máy in nhiệt ESC/POS nội bộ)
- Dành cho các shop muốn gửi lệnh in trực tiếp tới máy in nhiệt qua cổng LAN/USB thông qua dịch vụ cầu nối chạy tại `PRINT_BRIDGE_URL` (mặc định `http://127.0.0.1:9100/print`).
- Nếu dịch vụ cầu nối chưa bật hoặc máy in hết giấy/mất kết nối, lệnh in được đánh dấu `FAILED` kèm thông báo lỗi cụ thể, nhưng **đơn hàng đã chốt tuyệt đối không bị mất hoặc lỗi theo**. Nhân viên có thể bấm **In lại (Reprint)** bất kỳ lúc nào.
