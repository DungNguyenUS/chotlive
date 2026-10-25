export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function formatVND(amount: number | undefined | null): string {
  if (amount === undefined || amount === null || Number.isNaN(amount)) {
    return "0đ";
  }
  return `${Math.round(amount).toLocaleString("vi-VN")}đ`;
}

export function getConnectionBadgeInfo(mode: string): {
  label: string;
  className: string;
} {
  switch (mode) {
    case "CONNECTED":
      return {
        label: "CONNECTED (API Thật)",
        className: "bg-emerald-100 text-emerald-800 border-emerald-300",
      };
    case "DEMO":
      return {
        label: "DEMO (Mô Phỏng)",
        className: "bg-amber-100 text-amber-800 border-amber-300",
      };
    case "MANUAL_MODE":
      return {
        label: "MANUAL_MODE (Thủ Công Hợp Pháp)",
        className: "bg-blue-100 text-blue-800 border-blue-300",
      };
    case "NEEDS_PERMISSION":
      return {
        label: "NEEDS_PERMISSION (Thiếu Quyền Meta)",
        className: "bg-orange-100 text-orange-800 border-orange-300",
      };
    case "FAILED":
    case "MISSING_CREDENTIALS":
    default:
      return {
        label: `${mode || "DISCONNECTED"}`,
        className: "bg-rose-100 text-rose-800 border-rose-300",
      };
  }
}

export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errDetail: any = `Lỗi HTTP ${res.status}`;
    try {
      const data = await res.json();
      errDetail = data.detail || data;
    } catch {
      // ignore json parse error
    }
    const error = new Error(
      typeof errDetail === "string"
        ? errDetail
        : errDetail?.message || JSON.stringify(errDetail)
    ) as Error & { status?: number; payload?: any };
    error.status = res.status;
    error.payload = errDetail;
    throw error;
  }

  return res.json() as Promise<T>;
}
