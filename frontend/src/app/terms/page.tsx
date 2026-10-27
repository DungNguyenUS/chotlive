import type { Metadata } from "next";
import LegalLayout, { LEGAL_APP_NAME, LEGAL_CONTACT_EMAIL } from "../legal/LegalLayout";

export const metadata: Metadata = {
  title: `Điều khoản dịch vụ - ${LEGAL_APP_NAME}`,
};

export default function TermsPage() {
  return (
    <LegalLayout title="Điều Khoản Dịch Vụ (Terms of Service)">
      <p>
        Khi sử dụng {LEGAL_APP_NAME}, bạn đồng ý với các điều khoản dưới đây.
      </p>

      <h2>1. Dịch vụ</h2>
      <p>
        {LEGAL_APP_NAME} cung cấp công cụ đọc bình luận livestream trên Fanpage Facebook mà
        bạn quản lý, hỗ trợ chốt đơn, quản lý đơn hàng, in phiếu và gửi tin nhắn xác nhận đơn.
      </p>

      <h2>2. Trách nhiệm của người dùng</h2>
      <ul>
        <li>Chỉ kết nối những Fanpage mà bạn có quyền quản trị hợp pháp.</li>
        <li>
          Tuân thủ Tiêu chuẩn cộng đồng, Chính sách Nền tảng Meta và Chính sách Messenger của
          Facebook; không dùng {LEGAL_APP_NAME} để gửi spam hay tin nhắn quảng cáo không được
          phép.
        </li>
        <li>Tự bảo mật mật khẩu tài khoản {LEGAL_APP_NAME} của mình.</li>
      </ul>

      <h2>3. Giới hạn trách nhiệm</h2>
      <p>
        Dịch vụ phụ thuộc vào API của Meta. Chúng tôi không chịu trách nhiệm khi Facebook thay
        đổi, giới hạn hoặc tạm ngưng API ngoài tầm kiểm soát của chúng tôi.
      </p>

      <h2>4. Chấm dứt</h2>
      <p>
        Bạn có thể ngừng sử dụng và yêu cầu xóa dữ liệu bất kỳ lúc nào theo{" "}
        <a href="/data-deletion" className="underline text-blue-700">hướng dẫn xóa dữ
        liệu</a>.
      </p>

      <h2>5. Liên hệ</h2>
      <p>
        Email:{" "}
        <a href={`mailto:${LEGAL_CONTACT_EMAIL}`} className="underline text-blue-700">
          {LEGAL_CONTACT_EMAIL}
        </a>
      </p>
    </LegalLayout>
  );
}
