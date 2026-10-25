import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ChotLive - Hệ Thống Chốt Đơn Livestream Facebook",
  description:
    "Quản lý chốt đơn livestream cho Fanpage (Meta Graph API) và Trang Cá Nhân (Manual Mode hợp pháp).",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
