import Link from "next/link";

export const LEGAL_APP_NAME = "ChotLive";
export const LEGAL_CONTACT_EMAIL =
  process.env.NEXT_PUBLIC_CONTACT_EMAIL || "owner@chotlive.vn";
export const LEGAL_UPDATED_AT = "27/10/2026";

export default function LegalLayout({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="bg-slate-900 text-white">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="font-extrabold text-lg">
            {LEGAL_APP_NAME}
          </Link>
          <nav className="flex gap-4 text-xs text-slate-300">
            <Link href="/privacy" className="hover:text-white">
              Quyền riêng tư
            </Link>
            <Link href="/terms" className="hover:text-white">
              Điều khoản
            </Link>
            <Link href="/data-deletion" className="hover:text-white">
              Xóa dữ liệu
            </Link>
          </nav>
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-extrabold text-slate-900">{title}</h1>
        <p className="text-xs text-slate-500 mt-1">
          Cập nhật lần cuối: {LEGAL_UPDATED_AT}
        </p>
        <article className="mt-6 space-y-5 text-sm leading-relaxed [&_h2]:text-base [&_h2]:font-bold [&_h2]:text-slate-900 [&_h2]:mt-6 [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:space-y-1 [&_ol]:list-decimal [&_ol]:pl-6 [&_ol]:space-y-1">
          {children}
        </article>
      </main>
      <footer className="max-w-3xl mx-auto px-4 py-6 text-xs text-slate-500 border-t border-slate-200">
        © 2026 {LEGAL_APP_NAME} • Liên hệ:{" "}
        <a href={`mailto:${LEGAL_CONTACT_EMAIL}`} className="underline">
          {LEGAL_CONTACT_EMAIL}
        </a>
      </footer>
    </div>
  );
}
