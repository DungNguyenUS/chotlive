import type { Metadata } from "next";
import LegalLayout, { LEGAL_APP_NAME, LEGAL_CONTACT_EMAIL } from "../legal/LegalLayout";

export const metadata: Metadata = {
  title: `Chính sách quyền riêng tư - ${LEGAL_APP_NAME}`,
};

export default function PrivacyPolicyPage() {
  return (
    <LegalLayout title="Chính Sách Quyền Riêng Tư (Privacy Policy)">
      <p>
        {LEGAL_APP_NAME} là phần mềm hỗ trợ chủ shop bán hàng qua livestream trên Facebook
        Fanpage: đọc bình luận, nhận diện bình luận chốt đơn, tạo đơn hàng, in phiếu và gửi
        tin nhắn xác nhận đơn cho khách. Chính sách này giải thích chúng tôi thu thập, sử
        dụng, lưu trữ và xóa dữ liệu như thế nào.
      </p>

      <h2>1. Dữ liệu chúng tôi thu thập</h2>
      <ul>
        <li>
          <strong>Tài khoản {LEGAL_APP_NAME}:</strong> email, họ tên và mật khẩu (được mã hóa
          một chiều) do chủ shop tự đăng ký.
        </li>
        <li>
          <strong>Dữ liệu từ Facebook (khi chủ shop bấm “Kết Nối Nhanh Facebook”):</strong>
          danh sách Fanpage mà chủ shop chọn cấp quyền (ID, tên Trang) và Page Access Token
          của các Trang đó. Token được mã hóa (Fernet/AES) trước khi lưu.
        </li>
        <li>
          <strong>Bình luận trên bài viết / video livestream của Fanpage:</strong> nội dung
          bình luận, thời gian, ID và tên hiển thị công khai của người bình luận.
        </li>
        <li>
          <strong>Dữ liệu đơn hàng:</strong> sản phẩm, số lượng, thông tin giao hàng do chủ
          shop hoặc khách cung cấp.
        </li>
      </ul>

      <h2>2. Các quyền Facebook chúng tôi yêu cầu và mục đích</h2>
      <ul>
        <li>
          <code>pages_show_list</code>: hiển thị danh sách Fanpage để chủ shop chọn Trang cần
          kết nối.
        </li>
        <li>
          <code>pages_read_engagement</code>, <code>pages_read_user_content</code>: đọc bài
          viết, video livestream và bình luận trên Fanpage của chủ shop để nhận diện bình luận
          chốt đơn.
        </li>
        <li>
          <code>pages_manage_metadata</code>: đăng ký Webhook để nhận bình luận mới theo thời
          gian thực.
        </li>
        <li>
          <code>pages_messaging</code>: gửi tin nhắn xác nhận đơn hàng (Private Reply) tới
          khách hàng đã bình luận chốt đơn, chỉ khi chủ shop bấm xác nhận.
        </li>
      </ul>

      <h2>3. Cách chúng tôi sử dụng dữ liệu</h2>
      <ul>
        <li>Chỉ để cung cấp tính năng chốt đơn, quản lý đơn hàng và in phiếu cho chủ shop.</li>
        <li>
          <strong>Không</strong> bán, cho thuê hay chia sẻ dữ liệu cho bên thứ ba vì mục đích
          quảng cáo.
        </li>
        <li>
          Không dùng dữ liệu Facebook để xây dựng hồ sơ người dùng, theo dõi hay quảng cáo.
        </li>
        <li>
          Dữ liệu của mỗi cửa hàng được tách biệt; chỉ chủ shop và nhân viên được chủ shop
          phân quyền mới xem được.
        </li>
      </ul>

      <h2>4. Lưu trữ và bảo mật</h2>
      <ul>
        <li>Dữ liệu được lưu trên máy chủ có mã hóa đường truyền HTTPS.</li>
        <li>Access Token được mã hóa khi lưu, không hiển thị lại cho bất kỳ ai.</li>
        <li>
          Dữ liệu được giữ trong thời gian chủ shop còn sử dụng dịch vụ, và bị xóa khi chủ
          shop yêu cầu xóa hoặc gỡ ứng dụng khỏi Facebook.
        </li>
      </ul>

      <h2>5. Quyền của bạn và cách xóa dữ liệu</h2>
      <p>
        Bạn có thể ngắt kết nối và yêu cầu xóa toàn bộ dữ liệu bất kỳ lúc nào. Xem hướng dẫn
        chi tiết tại trang <a href="/data-deletion" className="underline text-blue-700">Hướng
        dẫn xóa dữ liệu</a>.
      </p>

      <h2>6. Liên hệ</h2>
      <p>
        Mọi câu hỏi về quyền riêng tư, vui lòng gửi email tới{" "}
        <a href={`mailto:${LEGAL_CONTACT_EMAIL}`} className="underline text-blue-700">
          {LEGAL_CONTACT_EMAIL}
        </a>
        .
      </p>
    </LegalLayout>
  );
}
