import type { Metadata } from "next";
import LegalLayout, { LEGAL_APP_NAME, LEGAL_CONTACT_EMAIL } from "../legal/LegalLayout";

export const metadata: Metadata = {
  title: `Hướng dẫn xóa dữ liệu - ${LEGAL_APP_NAME}`,
};

export default function DataDeletionPage() {
  return (
    <LegalLayout title="Hướng Dẫn Xóa Dữ Liệu (Data Deletion Instructions)">
      <p>
        Bạn có toàn quyền ngắt kết nối {LEGAL_APP_NAME} khỏi Facebook và yêu cầu xóa toàn bộ
        dữ liệu của mình. Chọn một trong các cách sau:
      </p>

      <h2>Cách 1: Gỡ ứng dụng trực tiếp trên Facebook</h2>
      <ol>
        <li>
          Mở Facebook → <strong>Cài đặt &amp; quyền riêng tư</strong> →{" "}
          <strong>Cài đặt</strong>.
        </li>
        <li>
          Chọn <strong>Tích hợp kinh doanh</strong> (Business Integrations) hoặc{" "}
          <strong>Ứng dụng và trang web</strong>.
        </li>
        <li>
          Tìm <strong>{LEGAL_APP_NAME}</strong> → bấm <strong>Gỡ</strong> (Remove).
        </li>
      </ol>
      <p>
        Ngay khi gỡ, Facebook thu hồi mọi Access Token, {LEGAL_APP_NAME} không thể đọc thêm
        bất kỳ dữ liệu nào từ Fanpage của bạn.
      </p>

      <h2>Cách 2: Yêu cầu xóa toàn bộ dữ liệu đã lưu</h2>
      <p>
        Gửi email tới{" "}
        <a
          href={`mailto:${LEGAL_CONTACT_EMAIL}?subject=Yeu%20cau%20xoa%20du%20lieu%20ChotLive`}
          className="underline text-blue-700"
        >
          {LEGAL_CONTACT_EMAIL}
        </a>{" "}
        với tiêu đề <em>“Yêu cầu xóa dữ liệu ChotLive”</em>, kèm email tài khoản{" "}
        {LEGAL_APP_NAME} hoặc tên / ID Fanpage của bạn.
      </p>
      <p>Trong vòng tối đa 30 ngày, chúng tôi sẽ xóa vĩnh viễn:</p>
      <ul>
        <li>Access Token và thông tin Fanpage đã kết nối;</li>
        <li>Bình luận, đơn hàng, thông tin khách hàng thuộc cửa hàng của bạn;</li>
        <li>Tài khoản {LEGAL_APP_NAME} của bạn (nếu bạn yêu cầu).</li>
      </ul>
      <p>Chúng tôi sẽ gửi email xác nhận khi việc xóa hoàn tất.</p>
    </LegalLayout>
  );
}
