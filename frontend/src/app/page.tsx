"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  apiFetch,
  formatVND,
  getConnectionBadgeInfo,
} from "@/lib/api";

type TabKey =
  | "comments"
  | "orders"
  | "products"
  | "sessions"
  | "messages"
  | "prints"
  | "print_settings"
  | "members"
  | "audit"
  | "health";

export default function ChotLiveApp() {
  // Auth & Shop State
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<any | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("owner@chotlive.vn");
  const [password, setPassword] = useState("ChotLive@2026");
  const [fullName, setFullName] = useState("Nguyễn Thu Hằng");
  const [authError, setAuthError] = useState<string | null>(null);
  const [isSubmittingAuth, setIsSubmittingAuth] = useState(false);

  const [shops, setShops] = useState<any[]>([]);
  const [activeShop, setActiveShop] = useState<any | null>(null);
  const [showCreateShopModal, setShowCreateShopModal] = useState(false);
  const [newShopName, setNewShopName] = useState("");
  const [newShopPhone, setNewShopPhone] = useState("");
  const [newShopPaperSize, setNewShopPaperSize] = useState("80mm");

  // Navigation & Filters
  const [activeTab, setActiveTab] = useState<TabKey>("comments");
  const [searchQuery, setSearchQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sessionFilter, setSessionFilter] = useState("");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");

  // Data States
  const [isLoading, setIsLoading] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const [dashboard, setDashboard] = useState<any | null>(null);
  const [comments, setComments] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [liveSessions, setLiveSessions] = useState<any[]>([]);
  const [connectedAccounts, setConnectedAccounts] = useState<any[]>([]);
  const [messages, setMessages] = useState<any[]>([]);
  const [printJobs, setPrintJobs] = useState<any[]>([]);
  const [printSettings, setPrintSettings] = useState<any | null>(null);
  const [members, setMembers] = useState<any[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [healthInfo, setHealthInfo] = useState<any | null>(null);
  const [metaStatus, setMetaStatus] = useState<any | null>(null);

  // Modals & Interactive Workflows
  const [selectedComment, setSelectedComment] = useState<any | null>(null);
  const [confirmModalComment, setConfirmModalComment] = useState<any | null>(null);
  const [confirmProductCode, setConfirmProductCode] = useState("");
  const [confirmQuantity, setConfirmQuantity] = useState(1);
  const [confirmColor, setConfirmColor] = useState("");
  const [confirmSize, setConfirmSize] = useState("");
  const [confirmNotes, setConfirmNotes] = useState("");
  const [confirmingCommentIds, setConfirmingCommentIds] = useState<Record<string, boolean>>({});

  const [selectedOrder, setSelectedOrder] = useState<any | null>(null);
  const [previewPrintJob, setPreviewPrintJob] = useState<any | null>(null);

  // Quick Manual Comment Input
  const [manualCommenterName, setManualCommenterName] = useState("");
  const [manualCommentText, setManualCommentText] = useState("");
  const [manualSessionId, setManualSessionId] = useState("");

  // Product Form
  const [newProdCode, setNewProdCode] = useState("");
  const [newProdName, setNewProdName] = useState("");
  const [newProdPrice, setNewProdPrice] = useState("");
  const [newProdStock, setNewProdStock] = useState("50");

  // Session & Account Form
  const [newSessionTitle, setNewSessionTitle] = useState("");
  const [newSessionSource, setNewSessionSource] = useState("DEMO");
  const [newSessionVideoId, setNewSessionVideoId] = useState("");
  const [newSessionConnectedAccountId, setNewSessionConnectedAccountId] = useState("");
  const [newAccPlatform, setNewAccPlatform] = useState("FACEBOOK_PAGE");
  const [newAccName, setNewAccName] = useState("");
  const [newAccExtId, setNewAccExtId] = useState("");
  const [newAccToken, setNewAccToken] = useState("");
  const [isSyncingComments, setIsSyncingComments] = useState(false);

  // Member Form
  const [newMemberEmail, setNewMemberEmail] = useState("");
  const [newMemberName, setNewMemberName] = useState("");
  const [newMemberRole, setNewMemberRole] = useState("STAFF");

  const notify = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 4000);
  };

  // Restore session from localStorage so refresh never loses data
  useEffect(() => {
    const savedToken = window.localStorage.getItem("chotlive_token");
    if (savedToken) {
      setToken(savedToken);
    }
  }, []);

  const loadInitialWorkspace = useCallback(async (jwt: string) => {
    setIsLoading(true);
    setGlobalError(null);
    try {
      const [me, shopList, health, meta] = await Promise.all([
        apiFetch("/auth/me", {}, jwt),
        apiFetch("/shops", {}, jwt),
        apiFetch("/health", {}, jwt),
        apiFetch("/meta/integration-status", {}, jwt),
      ]);
      setUser(me);
      setShops(shopList);
      setHealthInfo(health);
      setMetaStatus(meta);
      if (shopList.length > 0) {
        setActiveShop((prev: any) => prev || shopList[0]);
      } else {
        setShowCreateShopModal(true);
      }
    } catch (err: any) {
      if (err.status === 401) {
        window.localStorage.removeItem("chotlive_token");
        setToken(null);
        setUser(null);
      } else {
        setGlobalError(err.message || "Không thể kết nối máy chủ API.");
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (token) {
      loadInitialWorkspace(token);
    }
  }, [token, loadInitialWorkspace]);

  const loadShopData = useCallback(async () => {
    if (!token || !activeShop) return;
    setIsLoading(true);
    setGlobalError(null);
    try {
      const params = new URLSearchParams();
      if (searchQuery.trim()) params.set("q", searchQuery.trim());
      if (sourceFilter) params.set("source_type", sourceFilter);
      if (statusFilter) params.set("status", statusFilter);
      if (sessionFilter) params.set("live_session_id", sessionFilter);
      params.set("sort", sortOrder);

      const dashParams = new URLSearchParams();
      if (sessionFilter) dashParams.set("live_session_id", sessionFilter);

      const [
        dashData,
        cmtData,
        ordData,
        prodData,
        sessData,
        accData,
        msgData,
        prtData,
        pSetData,
        memData,
        audData,
      ] = await Promise.all([
        apiFetch(`/shops/${activeShop.id}/dashboard?${dashParams.toString()}`, {}, token),
        apiFetch(`/shops/${activeShop.id}/comments?${params.toString()}`, {}, token),
        apiFetch(`/shops/${activeShop.id}/orders`, {}, token),
        apiFetch(`/shops/${activeShop.id}/products`, {}, token),
        apiFetch(`/shops/${activeShop.id}/live-sessions`, {}, token),
        apiFetch(`/shops/${activeShop.id}/connected-accounts`, {}, token),
        apiFetch(`/shops/${activeShop.id}/messages`, {}, token),
        apiFetch(`/shops/${activeShop.id}/print-jobs`, {}, token),
        apiFetch(`/shops/${activeShop.id}/print-settings`, {}, token),
        apiFetch(`/shops/${activeShop.id}/members`, {}, token),
        apiFetch(`/shops/${activeShop.id}/audit-logs`, {}, token),
      ]);

      setDashboard(dashData);
      setComments(cmtData);
      setOrders(ordData);
      setProducts(prodData);
      setLiveSessions(sessData);
      if (sessData.length > 0 && !manualSessionId) {
        setManualSessionId(sessData[0].id);
      }
      setConnectedAccounts(accData);
      setMessages(msgData);
      setPrintJobs(prtData);
      setPrintSettings(pSetData);
      setMembers(memData);
      setAuditLogs(audData);
    } catch (err: any) {
      setGlobalError(err.message || "Lỗi tải dữ liệu cửa hàng.");
    } finally {
      setIsLoading(false);
    }
  }, [
    token,
    activeShop,
    searchQuery,
    sourceFilter,
    statusFilter,
    sessionFilter,
    sortOrder,
    manualSessionId,
  ]);

  useEffect(() => {
    if (token && activeShop) {
      loadShopData();
      const timer = setInterval(() => {
        if (activeTab === "comments" || activeTab === "orders") {
          loadShopData();
        }
      }, 4000);
      return () => clearInterval(timer);
    }
  }, [token, activeShop, activeTab, loadShopData]);

  // Handlers
  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    setIsSubmittingAuth(true);
    try {
      const endpoint = authMode === "login" ? "/auth/login" : "/auth/register";
      const body =
        authMode === "login"
          ? { email, password }
          : { email, full_name: fullName, password };
      const res = await apiFetch(endpoint, {
        method: "POST",
        body: JSON.stringify(body),
      });
      window.localStorage.setItem("chotlive_token", res.access_token);
      setToken(res.access_token);
      setUser(res.user);
    } catch (err: any) {
      setAuthError(err.message || "Đăng nhập thất bại.");
    } finally {
      setIsSubmittingAuth(false);
    }
  };

  const handleCreateShop = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !newShopName.trim()) return;
    try {
      const created = await apiFetch(
        "/shops",
        {
          method: "POST",
          body: JSON.stringify({
            name: newShopName.trim(),
            phone: newShopPhone.trim() || null,
            print_paper_size: newShopPaperSize,
            stt_reset_rule: "DAILY",
          }),
        },
        token
      );
      setShops((prev) => [...prev, created]);
      setActiveShop(created);
      setShowCreateShopModal(false);
      setNewShopName("");
      notify(`Đã tạo cửa hàng "${created.name}" thành công!`);
    } catch (err: any) {
      notify(err.message);
    }
  };

  const openConfirmModal = (comment: any) => {
    setConfirmModalComment(comment);
    setConfirmProductCode(comment.parsed_product_code || (products[0]?.code ?? ""));
    setConfirmQuantity(comment.parsed_quantity || 1);
    setConfirmColor(comment.parsed_color || "");
    setConfirmSize(comment.parsed_size || "");
    setConfirmNotes("");
  };

  const executeConfirmOrder = async (
    comment: any,
    explicitOverrides?: {
      product_code?: string;
      quantity?: number;
      color?: string;
      size?: string;
      notes?: string;
      force_confirm_ambiguous?: boolean;
    }
  ) => {
    if (!token || !activeShop) return;
    if (confirmingCommentIds[comment.id]) return; // Prevent double click in UI

    setConfirmingCommentIds((prev) => ({ ...prev, [comment.id]: true }));
    try {
      const idemKey = `ui_confirm_${comment.id}`;
      const res = await apiFetch(
        `/shops/${activeShop.id}/orders/confirm`,
        {
          method: "POST",
          body: JSON.stringify({
            comment_id: comment.id,
            idempotency_key: idemKey,
            ...explicitOverrides,
          }),
        },
        token
      );
      setConfirmModalComment(null);
      notify(
        res.was_idempotent_replay
          ? `Đơn ${res.order.order_code} đã được chốt trước đó (Chống trùng tự động).`
          : `ĐÃ CHỐT thành công đơn ${res.order.order_code} (STT #${String(
              res.order.customer_stt
            ).padStart(2, "0")})!`
      );
      if (res.print_job && activeShop.confirm_before_print) {
        setPreviewPrintJob(res.print_job);
      }
      await loadShopData();
    } catch (err: any) {
      if (err.status === 422) {
        // Ambiguous comment -> open confirmation modal for staff
        openConfirmModal(comment);
      } else {
        notify(err.message || "Không thể chốt đơn.");
      }
    } finally {
      setConfirmingCommentIds((prev) => ({ ...prev, [comment.id]: false }));
    }
  };

  const handleAddManualComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !activeShop || !manualSessionId || !manualCommenterName.trim() || !manualCommentText.trim()) {
      return;
    }
    try {
      await apiFetch(
        `/shops/${activeShop.id}/comments`,
        {
          method: "POST",
          body: JSON.stringify({
            live_session_id: manualSessionId,
            commenter_name: manualCommenterName.trim(),
            raw_message: manualCommentText.trim(),
          }),
        },
        token
      );
      setManualCommenterName("");
      setManualCommentText("");
      notify("Đã tiếp nhận bình luận vào danh sách xử lý!");
      await loadShopData();
    } catch (err: any) {
      notify(err.message);
    }
  };

  const handleCreateProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !activeShop) return;
    try {
      await apiFetch(
        `/shops/${activeShop.id}/products`,
        {
          method: "POST",
          body: JSON.stringify({
            code: newProdCode.trim().toUpperCase(),
            name: newProdName.trim(),
            unit_price: Number(newProdPrice),
            stock_quantity: Number(newProdStock || 0),
          }),
        },
        token
      );
      setNewProdCode("");
      setNewProdName("");
      setNewProdPrice("");
      notify("Đã thêm sản phẩm mới!");
      await loadShopData();
    } catch (err: any) {
      notify(err.message);
    }
  };

  const handleCreateLiveSession = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !activeShop || !newSessionTitle.trim()) return;
    try {
      await apiFetch(
        `/shops/${activeShop.id}/live-sessions`,
        {
          method: "POST",
          body: JSON.stringify({
            title: newSessionTitle.trim(),
            source_type: newSessionSource,
            external_video_id: newSessionVideoId.trim() || undefined,
            connected_account_id: newSessionConnectedAccountId || undefined,
          }),
        },
        token
      );
      setNewSessionTitle("");
      setNewSessionVideoId("");
      notify("Đã tạo phiên livestream mới!");
      await loadShopData();
    } catch (err: any) {
      notify(err.message);
    }
  };

  const handleConnectAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !activeShop || !newAccName.trim() || !newAccExtId.trim()) return;
    try {
      await apiFetch(
        `/shops/${activeShop.id}/connected-accounts`,
        {
          method: "POST",
          body: JSON.stringify({
            platform: newAccPlatform,
            name: newAccName.trim(),
            external_id: newAccExtId.trim(),
            access_token: newAccToken.trim() || undefined,
          }),
        },
        token
      );
      setNewAccName("");
      setNewAccExtId("");
      setNewAccToken("");
      notify("Đã lưu cấu hình nguồn livestream!");
      await loadShopData();
    } catch (err: any) {
      notify(err.message);
    }
  };

  const handleSyncFacebookComments = async (sessionId: string) => {
    if (!token || !activeShop || !sessionId) return;
    setIsSyncingComments(true);
    try {
      const res = await apiFetch(
        `/shops/${activeShop.id}/live-sessions/${sessionId}/sync-facebook-comments`,
        { method: "POST" },
        token
      );
      notify(
        `Đã quét ${res.total_fetched_from_facebook} bình luận từ Facebook, thêm mới ${res.new_comments_ingested} bình luận!`
      );
      await loadShopData();
    } catch (err: any) {
      notify(err.message || "Không thể đồng bộ bình luận từ Facebook.");
    } finally {
      setIsSyncingComments(false);
    }
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !activeShop || !newMemberEmail.trim()) return;
    try {
      await apiFetch(
        `/shops/${activeShop.id}/members`,
        {
          method: "POST",
          body: JSON.stringify({
            email: newMemberEmail.trim(),
            full_name: newMemberName.trim() || "Nhân Viên Shop",
            role: newMemberRole,
          }),
        },
        token
      );
      setNewMemberEmail("");
      setNewMemberName("");
      notify("Đã phân quyền nhân sự thành công!");
      await loadShopData();
    } catch (err: any) {
      notify(err.message);
    }
  };

  const handleOpenBrowserPrint = async (job: any) => {
    if (!token || !activeShop) return;
    // Per requirement: Opening browser print dialog sets status to PRINTING, NEVER automatically PRINTED!
    try {
      const updated = await apiFetch(
        `/shops/${activeShop.id}/print-jobs/${job.id}/status?new_status=PRINTING`,
        { method: "PATCH" },
        token
      );
      setPreviewPrintJob(updated);
      const printWin = window.open("", "_blank", "width=450,height=650");
      if (printWin) {
        printWin.document.open();
        printWin.document.write(job.rendered_html);
        printWin.document.close();
        printWin.focus();
        printWin.print();
      }
      await loadShopData();
    } catch (err: any) {
      notify(err.message);
    }
  };

  const handleUpdatePrintStatus = async (jobId: string, newStatus: string) => {
    if (!token || !activeShop) return;
    try {
      const updated = await apiFetch(
        `/shops/${activeShop.id}/print-jobs/${jobId}/status?new_status=${newStatus}`,
        { method: "PATCH" },
        token
      );
      setPreviewPrintJob(updated);
      notify(`Đã cập nhật trạng thái phiếu in: ${newStatus}`);
      await loadShopData();
    } catch (err: any) {
      notify(err.message);
    }
  };

  const selectedModalProduct = useMemo(() => {
    return products.find((p) => p.code === confirmProductCode.toUpperCase());
  }, [products, confirmProductCode]);

  // ============================================================================
  // SCREEN 1: LOGIN / REGISTER
  // ============================================================================
  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 p-4">
        <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-6 sm:p-8">
          <div className="flex items-center gap-3 mb-6">
            <span className="px-3 py-1 bg-rose-600 text-white font-black rounded-lg text-sm tracking-wider">
              LIVE
            </span>
            <div>
              <h1 className="text-2xl font-extrabold text-slate-900">
                ChotLive Việt Nam
              </h1>
              <p className="text-xs text-slate-500">
                Hệ thống quản lý chốt đơn Fanpage & Trang Cá Nhân
              </p>
            </div>
          </div>

          <div className="flex rounded-lg bg-slate-100 p-1 mb-6">
            <button
              type="button"
              onClick={() => setAuthMode("login")}
              className={`flex-1 py-2 text-sm font-bold rounded-md transition ${
                authMode === "login"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600"
              }`}
            >
              Đăng Nhập
            </button>
            <button
              type="button"
              onClick={() => setAuthMode("register")}
              className={`flex-1 py-2 text-sm font-bold rounded-md transition ${
                authMode === "register"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600"
              }`}
            >
              Đăng Ký Tài Khoản
            </button>
          </div>

          {authError && (
            <div
              role="alert"
              className="mb-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm font-medium"
            >
              {authError}
            </div>
          )}

          <form onSubmit={handleAuthSubmit} className="space-y-4">
            {authMode === "register" && (
              <div>
                <label className="block text-xs font-bold uppercase text-slate-700 mb-1">
                  Họ và tên
                </label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-indigo-600 outline-none"
                  placeholder="Nguyễn Thu Hằng"
                />
              </div>
            )}
            <div>
              <label className="block text-xs font-bold uppercase text-slate-700 mb-1">
                Email đăng nhập
              </label>
              <input
                type="email"
                required
                data-testid="login-email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-indigo-600 outline-none"
                placeholder="owner@chotlive.vn"
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase text-slate-700 mb-1">
                Mật khẩu
              </label>
              <input
                type="password"
                required
                data-testid="login-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-indigo-600 outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={isSubmittingAuth}
              data-testid="login-submit"
              className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-bold text-sm shadow-md transition"
            >
              {isSubmittingAuth
                ? "Đang xử lý..."
                : authMode === "login"
                ? "Đăng Nhập Hệ Thống"
                : "Tạo Tài Khoản Mới"}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-slate-200 text-xs text-slate-500 space-y-1">
            <p className="font-semibold text-slate-700">
              Cam kết bảo mật & tuân thủ Meta:
            </p>
            <p>
              • Không bao giờ yêu cầu mật khẩu Facebook của bạn. Kết nối Fanpage
              qua OAuth chính thức của Meta.
            </p>
            <p>
              • Tài khoản mẫu Dev: <code>owner@chotlive.vn</code> /{" "}
              <code>ChotLive@2026</code>
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ============================================================================
  // MAIN WORKSPACE (MOBILE-FIRST + DESKTOP)
  // ============================================================================
  return (
    <div className="min-h-screen flex flex-col bg-slate-50 pb-20">
      {/* Top Bar */}
      <header className="sticky top-0 z-30 bg-slate-900 text-white shadow-md">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <span className="px-2.5 py-1 bg-rose-600 text-white text-xs font-black rounded-md animate-pulse">
              LIVE
            </span>
            <div>
              <span className="font-extrabold text-base sm:text-lg tracking-tight">
                ChotLive
              </span>
              {activeShop && (
                <span className="ml-2 text-xs bg-slate-800 px-2.5 py-1 rounded-full text-slate-200 border border-slate-700">
                  Shop: {activeShop.name}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <select
              aria-label="Chọn cửa hàng"
              value={activeShop?.id || ""}
              onChange={(e) => {
                const found = shops.find((s) => s.id === e.target.value);
                if (found) setActiveShop(found);
              }}
              className="bg-slate-800 text-white text-xs rounded-lg px-2.5 py-1.5 border border-slate-700"
            >
              {shops.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setShowCreateShopModal(true)}
              className="text-xs bg-indigo-600 hover:bg-indigo-500 px-2.5 py-1.5 rounded-lg font-semibold"
            >
              + Tạo Shop
            </button>
            <button
              type="button"
              onClick={() => {
                window.localStorage.removeItem("chotlive_token");
                setToken(null);
                setUser(null);
              }}
              className="text-xs bg-slate-800 hover:bg-slate-700 px-2.5 py-1.5 rounded-lg text-slate-300"
            >
              Đăng xuất
            </button>
          </div>
        </div>

        {/* Large Mobile-First Search Bar & Quick Filters at Top of Screen */}
        <div className="bg-slate-800/90 border-t border-slate-700/80 px-3 sm:px-6 py-2.5">
          <div className="max-w-7xl mx-auto flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
              <input
                type="search"
                data-testid="global-search-input"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Tìm nhanh tên khách, mã hàng (VD: A50, B20), nội dung bình luận..."
                className="w-full pl-3.5 pr-4 py-2.5 rounded-xl bg-white text-slate-900 text-sm font-medium placeholder:text-slate-400 focus:ring-2 focus:ring-amber-400 outline-none"
              />
            </div>
            <div className="flex gap-1.5 overflow-x-auto pb-1 sm:pb-0">
              <select
                aria-label="Lọc nguồn livestream"
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                className="bg-slate-700 text-white text-xs rounded-xl px-3 py-2 border border-slate-600"
              >
                <option value="">Tất cả nguồn</option>
                <option value="FACEBOOK_PAGE">Fanpage (Meta API)</option>
                <option value="FACEBOOK_PERSONAL">Trang Cá Nhân (Thủ công)</option>
                <option value="DEMO">DEMO (Mô phỏng Dev)</option>
              </select>
              <select
                aria-label="Lọc trạng thái bình luận"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-slate-700 text-white text-xs rounded-xl px-3 py-2 border border-slate-600"
              >
                <option value="">Mọi trạng thái</option>
                <option value="PARSED">Sẵn sàng chốt (PARSED)</option>
                <option value="NEEDS_REVIEW">Cần kiểm tra mã (NEEDS_REVIEW)</option>
                <option value="CONFIRMED">Đã chốt đơn (CONFIRMED)</option>
                <option value="IGNORED">Đã bỏ qua / Hủy</option>
              </select>
              <button
                type="button"
                onClick={() =>
                  setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"))
                }
                className="bg-slate-700 hover:bg-slate-600 text-white text-xs rounded-xl px-3 py-2 border border-slate-600 whitespace-nowrap font-semibold"
              >
                {sortOrder === "asc"
                  ? "⏱ Ưu tiên khách bình luận trước"
                  : "⏱ Mới nhất lên đầu"}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Toast Notification */}
      {toastMsg && (
        <div
          role="status"
          data-testid="toast-notification"
          className="fixed bottom-16 right-4 z-50 bg-slate-900 text-white px-4 py-3 rounded-xl shadow-2xl border border-indigo-500 text-sm font-semibold max-w-sm"
        >
          {toastMsg}
        </div>
      )}

      {/* Disconnected / Error Banner */}
      {globalError && (
        <div
          role="alert"
          className="max-w-7xl mx-auto w-full mt-3 px-3 sm:px-6"
        >
          <div className="bg-rose-50 border border-rose-300 text-rose-800 px-4 py-3 rounded-xl flex items-center justify-between text-sm">
            <span>
              <strong>Mất kết nối hoặc lỗi tải dữ liệu:</strong> {globalError}
            </span>
            <button
              type="button"
              onClick={() => loadShopData()}
              className="px-3 py-1 bg-rose-700 text-white rounded-lg text-xs font-bold"
            >
              Thử lại
            </button>
          </div>
        </div>
      )}

      {/* 4 Primary Stat Cards (Mobile-First Grid) */}
      {dashboard && (
        <section
          aria-label="Thống kê nhanh"
          className="max-w-7xl mx-auto w-full px-3 sm:px-6 pt-3 grid grid-cols-2 lg:grid-cols-4 gap-2.5"
        >
          <div className="bg-white p-3.5 rounded-2xl shadow-sm border border-slate-200">
            <div className="text-xs font-semibold text-slate-500">
              Tổng Bình Luận / Đã Chốt
            </div>
            <div
              data-testid="stat-comments"
              className="text-xl sm:text-2xl font-black text-slate-900 mt-1"
            >
              {dashboard.total_comments}{" "}
              <span className="text-sm font-bold text-emerald-600">
                ({dashboard.confirmed_comments} đã chốt)
              </span>
            </div>
          </div>

          <div className="bg-white p-3.5 rounded-2xl shadow-sm border border-slate-200">
            <div className="text-xs font-semibold text-slate-500">
              Khách Đã Chốt / Đơn Hàng
            </div>
            <div
              data-testid="stat-customers-orders"
              className="text-xl sm:text-2xl font-black text-indigo-700 mt-1"
            >
              {dashboard.unique_confirmed_customers} khách{" "}
              <span className="text-sm font-bold text-slate-600">
                / {dashboard.total_orders} đơn
              </span>
            </div>
          </div>

          <div className="bg-white p-3.5 rounded-2xl shadow-sm border border-slate-200">
            <div className="text-xs font-semibold text-slate-500">
              Tin Nhắn / Phiếu In
            </div>
            <div className="text-xs sm:text-sm font-bold text-slate-800 mt-1.5 space-y-0.5">
              <div>
                Messenger:{" "}
                <span className="text-emerald-700">
                  {dashboard.messages_sent} gửi OK
                </span>{" "}
                •{" "}
                <span className="text-amber-700">
                  {dashboard.messages_pending_or_manual} chờ/thủ công
                </span>{" "}
                •{" "}
                <span className="text-rose-700">
                  {dashboard.messages_failed} lỗi
                </span>
              </div>
              <div>
                Máy in:{" "}
                <span className="text-emerald-700">
                  {dashboard.prints_printed} đã in
                </span>{" "}
                •{" "}
                <span className="text-amber-700">
                  {dashboard.prints_queued} hàng đợi
                </span>{" "}
                •{" "}
                <span className="text-rose-700">
                  {dashboard.prints_failed} lỗi
                </span>
              </div>
            </div>
          </div>

          <div className="bg-white p-3.5 rounded-2xl shadow-sm border border-slate-200">
            <div className="text-xs font-semibold text-slate-500">
              Doanh Thu Đơn Đã Xác Nhận
            </div>
            <div
              data-testid="stat-revenue"
              className="text-xl sm:text-2xl font-black text-emerald-700 mt-1"
            >
              {formatVND(dashboard.confirmed_revenue)}
            </div>
            <div className="text-[11px] text-slate-400">
              Không tính {dashboard.cancelled_orders} đơn đã hủy
            </div>
          </div>
        </section>
      )}

      {/* Navigation Tabs covering all 17 Functional Screens */}
      <nav className="max-w-7xl mx-auto w-full px-3 sm:px-6 mt-3">
        <div className="flex gap-1.5 overflow-x-auto bg-white p-1.5 rounded-2xl shadow-sm border border-slate-200">
          {[
            { id: "comments", label: "💬 Bình Luận & Chốt Đơn" },
            { id: "orders", label: `📦 Đơn Hàng (${orders.length})` },
            { id: "products", label: `🏷 Sản Phẩm (${products.length})` },
            { id: "sessions", label: "📡 Nguồn & Phiên Live" },
            { id: "messages", label: `✉️ Tin Nhắn (${messages.length})` },
            { id: "prints", label: `🖨 Hàng Đợi In (${printJobs.length})` },
            { id: "print_settings", label: "⚙️ Mẫu In & Tin Nhắn" },
            { id: "members", label: "👥 Nhân Viên & Vai Trò" },
            { id: "audit", label: "🛡 Nhật Ký Hoạt Động" },
            { id: "health", label: "🩺 Sức Khỏe Hệ Thống & Meta" },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              data-testid={`tab-${tab.id}`}
              onClick={() => setActiveTab(tab.id as TabKey)}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition ${
                activeTab === tab.id
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto w-full px-3 sm:px-6 mt-3 flex-1">
        {/* TAB 1: COMMENTS & CHỐT ĐƠN */}
        {activeTab === "comments" && (
          <div className="space-y-4">
            {/* Manual / Mock Comment Entry Bar */}
            <form
              onSubmit={handleAddManualComment}
              className="bg-white p-3.5 rounded-2xl shadow-sm border border-slate-200 flex flex-col md:flex-row gap-2 items-stretch md:items-center"
            >
              <select
                aria-label="Chọn phiên live để nhập bình luận"
                value={manualSessionId}
                onChange={(e) => setManualSessionId(e.target.value)}
                className="px-3 py-2 rounded-xl border border-slate-300 text-xs font-semibold bg-slate-50"
              >
                {liveSessions.map((s) => (
                  <option key={s.id} value={s.id}>
                    [{s.connection_mode}] {s.title}
                  </option>
                ))}
              </select>
              <input
                type="text"
                data-testid="manual-commenter-name"
                value={manualCommenterName}
                onChange={(e) => setManualCommenterName(e.target.value)}
                placeholder="Tên khách (VD: Chị Hằng)"
                className="px-3 py-2 rounded-xl border border-slate-300 text-xs"
              />
              <input
                type="text"
                data-testid="manual-comment-text"
                value={manualCommentText}
                onChange={(e) => setManualCommentText(e.target.value)}
                placeholder="Nội dung bình luận (VD: Chốt 2 áo A50 màu đỏ size M)"
                className="flex-1 px-3 py-2 rounded-xl border border-slate-300 text-xs"
              />
              <button
                type="submit"
                data-testid="manual-comment-submit"
                className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold whitespace-nowrap"
              >
                + Nhập Bình Luận
              </button>
              <button
                type="button"
                disabled={isSyncingComments || !manualSessionId}
                onClick={() => handleSyncFacebookComments(manualSessionId)}
                className="px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-bold whitespace-nowrap"
              >
                {isSyncingComments ? "⏳ Đang quét FB..." : "🔄 Quét Comment FB Thật"}
              </button>
            </form>

            {/* Comment Cards List */}
            {isLoading && comments.length === 0 ? (
              <div className="bg-white p-8 rounded-2xl text-center text-slate-500 text-sm">
                Đang tải danh sách bình luận livestream...
              </div>
            ) : comments.length === 0 ? (
              <div
                data-testid="comments-empty-state"
                className="bg-white p-8 rounded-2xl text-center border border-dashed border-slate-300"
              >
                <p className="text-sm font-bold text-slate-700">
                  Chưa có bình luận nào khớp với bộ lọc hiện tại.
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Hãy thử xóa từ khóa tìm kiếm hoặc nhập bình luận mới ở thanh
                  phía trên.
                </p>
              </div>
            ) : (
              <div className="space-y-2.5">
                {comments.map((cmt) => {
                  const badge = getConnectionBadgeInfo(cmt.connection_mode);
                  const isConfirmed = cmt.status === "CONFIRMED";
                  const isConfirming = Boolean(confirmingCommentIds[cmt.id]);

                  return (
                    <div
                      key={cmt.id}
                      data-testid={`comment-card-${cmt.external_comment_id}`}
                      className={`p-4 rounded-2xl border transition shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                        isConfirmed
                          ? "bg-emerald-50/60 border-emerald-300"
                          : cmt.is_ambiguous
                          ? "bg-amber-50/40 border-amber-300"
                          : "bg-white border-slate-200"
                      }`}
                    >
                      <div className="space-y-1.5 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="w-7 h-7 rounded-full bg-indigo-100 text-indigo-800 font-bold text-xs flex items-center justify-center">
                            {cmt.commenter_name.slice(0, 1).toUpperCase()}
                          </span>
                          <span className="font-extrabold text-slate-900 text-sm sm:text-base">
                            {cmt.commenter_name}
                          </span>
                          <span className="px-2 py-0.5 bg-rose-600 text-white text-[10px] font-black rounded">
                            LIVE
                          </span>
                          <span
                            className={`px-2 py-0.5 text-[11px] font-bold rounded border ${badge.className}`}
                          >
                            {badge.label}
                          </span>
                          <span className="text-xs text-slate-400">
                            {new Date(cmt.commented_at).toLocaleTimeString(
                              "vi-VN"
                            )}
                          </span>
                        </div>

                        <p className="text-slate-800 text-sm font-medium bg-slate-100/80 px-3 py-2 rounded-xl">
                          “{cmt.raw_message}”
                        </p>

                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          {cmt.parsed_product_code ? (
                            <span className="px-2.5 py-0.5 rounded-md bg-indigo-50 text-indigo-700 font-bold border border-indigo-200">
                              Mã SP: {cmt.parsed_product_code}
                            </span>
                          ) : (
                            <span className="px-2.5 py-0.5 rounded-md bg-amber-100 text-amber-800 font-bold">
                              Chưa rõ mã SP
                            </span>
                          )}
                          <span className="px-2.5 py-0.5 rounded-md bg-slate-100 text-slate-700 font-semibold">
                            SL: {cmt.parsed_quantity}
                          </span>
                          {cmt.parsed_color && (
                            <span className="px-2.5 py-0.5 rounded-md bg-slate-100 text-slate-700">
                              Màu: {cmt.parsed_color}
                            </span>
                          )}
                          {cmt.parsed_size && (
                            <span className="px-2.5 py-0.5 rounded-md bg-slate-100 text-slate-700">
                              Size: {cmt.parsed_size}
                            </span>
                          )}
                          <span className="text-slate-400">
                            Độ tin cậy: {Math.round(cmt.parse_confidence * 100)}%
                          </span>
                        </div>
                      </div>

                      {/* Prominent Thumb-Friendly Action Buttons */}
                      <div className="flex items-center gap-2 self-end sm:self-center">
                        <button
                          type="button"
                          onClick={() => setSelectedComment(cmt)}
                          className="px-3 py-2.5 rounded-xl border border-slate-300 text-slate-700 hover:bg-slate-100 text-xs font-bold"
                        >
                          Chi tiết
                        </button>

                        {isConfirmed ? (
                          <span
                            data-testid={`confirmed-badge-${cmt.external_comment_id}`}
                            className="px-4 py-2.5 rounded-xl bg-emerald-600 text-white text-xs font-black shadow-sm"
                          >
                            ✓ ĐÃ CHỐT ĐƠN
                          </span>
                        ) : (
                          <>
                            <button
                              type="button"
                              onClick={() => openConfirmModal(cmt)}
                              className="px-3 py-2.5 rounded-xl border border-indigo-300 text-indigo-700 hover:bg-indigo-50 text-xs font-bold"
                            >
                              Chọn SP
                            </button>
                            <button
                              type="button"
                              disabled={isConfirming}
                              data-testid={`btn-chot-${cmt.external_comment_id}`}
                              onClick={() => executeConfirmOrder(cmt)}
                              className="px-5 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 active:scale-95 disabled:opacity-50 text-white text-sm font-black shadow-md transition"
                            >
                              {isConfirming ? "ĐANG CHỐT..." : "ĐÃ CHỐT"}
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: ORDERS LIST & DETAIL */}
        {activeTab === "orders" && (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="font-extrabold text-base text-slate-900">
                Danh Sách Đơn Hàng Đã Chốt
              </h2>
            </div>
            {orders.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                Chưa có đơn hàng nào được tạo.
              </div>
            ) : (
              <div className="divide-y divide-slate-200">
                {orders.map((ord) => (
                  <div
                    key={ord.id}
                    data-testid={`order-row-${ord.order_code}`}
                    className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-0.5 bg-slate-900 text-white font-black text-xs rounded">
                          STT #{String(ord.customer_stt).padStart(2, "0")}
                        </span>
                        <span className="font-extrabold text-sm text-indigo-700">
                          {ord.order_code}
                        </span>
                        <span
                          className={`px-2 py-0.5 text-xs font-bold rounded ${
                            ord.status === "CONFIRMED"
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-rose-100 text-rose-800"
                          }`}
                        >
                          {ord.status}
                        </span>
                      </div>
                      {ord.items?.map((it: any) => (
                        <div key={it.id} className="text-xs text-slate-700">
                          <strong>{it.product_code_snapshot}</strong> -{" "}
                          {it.product_name_snapshot} ({it.variant_snapshot}) •{" "}
                          {it.quantity} x {formatVND(it.unit_price_snapshot)} ={" "}
                          <strong className="text-emerald-700">
                            {formatVND(it.line_total)}
                          </strong>
                        </div>
                      ))}
                      <div className="flex flex-wrap gap-3 text-[11px] text-slate-500">
                        <span>
                          Trạng thái Messenger:{" "}
                          <strong>
                            {ord.message_logs?.[0]?.status || "NONE"}
                          </strong>
                        </span>
                        <span>
                          Trạng thái In:{" "}
                          <strong>
                            {ord.print_jobs?.[0]?.status || "NONE"}
                          </strong>
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setSelectedOrder(ord)}
                        className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-bold"
                      >
                        Chi tiết
                      </button>
                      {ord.print_jobs?.[0] && (
                        <button
                          type="button"
                          onClick={() => setPreviewPrintJob(ord.print_jobs[0])}
                          className="px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-bold"
                        >
                          Xem Phiếu In
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: PRODUCTS & PRICES */}
        {activeTab === "products" && (
          <div className="space-y-4">
            <form
              onSubmit={handleCreateProduct}
              className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 grid grid-cols-1 sm:grid-cols-5 gap-2.5"
            >
              <input
                type="text"
                required
                data-testid="new-product-code"
                value={newProdCode}
                onChange={(e) => setNewProdCode(e.target.value)}
                placeholder="Mã SP (VD: D99)"
                className="px-3 py-2 rounded-xl border border-slate-300 text-xs font-bold uppercase"
              />
              <input
                type="text"
                required
                data-testid="new-product-name"
                value={newProdName}
                onChange={(e) => setNewProdName(e.target.value)}
                placeholder="Tên sản phẩm"
                className="sm:col-span-2 px-3 py-2 rounded-xl border border-slate-300 text-xs"
              />
              <input
                type="number"
                required
                min={0}
                data-testid="new-product-price"
                value={newProdPrice}
                onChange={(e) => setNewProdPrice(e.target.value)}
                placeholder="Giá bán (VNĐ)"
                className="px-3 py-2 rounded-xl border border-slate-300 text-xs"
              />
              <button
                type="submit"
                data-testid="new-product-submit"
                className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-bold"
              >
                + Thêm Sản Phẩm
              </button>
            </form>

            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 divide-y divide-slate-200">
              {products.map((p) => (
                <div
                  key={p.id}
                  className="p-4 flex items-center justify-between"
                >
                  <div>
                    <span className="px-2.5 py-1 bg-indigo-100 text-indigo-900 font-black text-xs rounded mr-2">
                      {p.code}
                    </span>
                    <span className="font-bold text-sm text-slate-900">
                      {p.name}
                    </span>
                    <span className="ml-3 text-xs text-slate-500">
                      Tồn kho: {p.stock_quantity}
                    </span>
                  </div>
                  <div className="font-black text-emerald-700 text-sm">
                    {formatVND(p.unit_price)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 4: CONNECTED ACCOUNTS & LIVE SESSIONS */}
        {activeTab === "sessions" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-100">
                <h3 className="font-extrabold text-sm text-slate-900">
                  1. Nguồn Kết Nối (Fanpage OAuth & Trang Cá Nhân)
                </h3>
                <button
                  type="button"
                  onClick={async () => {
                    if (!token || !activeShop) return;
                    try {
                      const res = await apiFetch(
                        `/shops/${activeShop.id}/meta/oauth-url`,
                        {},
                        token
                      );
                      if (res.oauth_url) {
                        window.location.href = res.oauth_url;
                      }
                    } catch (err: any) {
                      notify(err.message);
                    }
                  }}
                  className="px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-extrabold shadow-sm transition"
                >
                  🔗 Kết Nối Nhanh Facebook (1-Click OAuth Cho Khách Hàng)
                </button>
              </div>
              <form onSubmit={handleConnectAccount} className="space-y-2">
                <select
                  value={newAccPlatform}
                  onChange={(e) => setNewAccPlatform(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-semibold"
                >
                  <option value="FACEBOOK_PERSONAL">
                    Facebook Trang Cá Nhân (Chế độ MANUAL_MODE hợp pháp)
                  </option>
                  <option value="FACEBOOK_PAGE">
                    Facebook Fanpage (Meta Graph API chính thức)
                  </option>
                  <option value="DEMO">DEMO (Mô phỏng kiểm thử)</option>
                </select>
                <input
                  type="text"
                  value={newAccName}
                  onChange={(e) => setNewAccName(e.target.value)}
                  placeholder="Tên hiển thị Fanpage hoặc Trang cá nhân"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs"
                />
                <input
                  type="text"
                  value={newAccExtId}
                  onChange={(e) => setNewAccExtId(e.target.value)}
                  placeholder="Page ID của bạn (VD: 123456789012345)"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs"
                />
                {newAccPlatform === "FACEBOOK_PAGE" && (
                  <input
                    type="password"
                    value={newAccToken}
                    onChange={(e) => setNewAccToken(e.target.value)}
                    placeholder="Dán Page Access Token (Lấy từ Graph API Explorer để test thật)"
                    className="w-full px-3 py-2 rounded-xl border border-indigo-300 bg-indigo-50/40 text-xs"
                  />
                )}
                <button
                  type="submit"
                  className="w-full py-2 rounded-xl bg-slate-900 text-white text-xs font-bold"
                >
                  Lưu Nguồn Kết Nối
                </button>
              </form>

              <div className="divide-y divide-slate-200 pt-2">
                {connectedAccounts.map((acc) => {
                  const badge = getConnectionBadgeInfo(acc.connection_status);
                  return (
                    <div key={acc.id} className="py-2.5 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-900">
                          {acc.name}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded border font-bold ${badge.className}`}
                        >
                          {badge.label}
                        </span>
                      </div>
                      {acc.missing_permissions && (
                        <div className="text-orange-700 font-medium">
                          Quyền bị thiếu: {acc.missing_permissions}
                        </div>
                      )}
                      {acc.last_error && (
                        <div className="text-slate-500">{acc.last_error}</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 space-y-3">
              <h3 className="font-extrabold text-sm text-slate-900">
                2. Danh Sách Phiên Livestream
              </h3>
              <form onSubmit={handleCreateLiveSession} className="space-y-2">
                <input
                  type="text"
                  value={newSessionTitle}
                  onChange={(e) => setNewSessionTitle(e.target.value)}
                  placeholder="Tiêu đề phiên live (VD: Live Xả Kho Tối Chủ Nhật)"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs"
                />
                <select
                  value={newSessionSource}
                  onChange={(e) => setNewSessionSource(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-semibold"
                >
                  <option value="FACEBOOK_PAGE">
                    FACEBOOK_PAGE (Fanpage API Thật)
                  </option>
                  <option value="FACEBOOK_PERSONAL">
                    FACEBOOK_PERSONAL (Nhập thủ công)
                  </option>
                  <option value="DEMO">DEMO (Mô phỏng)</option>
                </select>
                {newSessionSource === "FACEBOOK_PAGE" && (
                  <>
                    <select
                      value={newSessionConnectedAccountId}
                      onChange={(e) => setNewSessionConnectedAccountId(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs"
                    >
                      <option value="">-- Chọn Fanpage đã kết nối --</option>
                      {connectedAccounts
                        .filter((a) => a.platform === "FACEBOOK_PAGE")
                        .map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.name} ({a.external_id})
                          </option>
                        ))}
                    </select>
                    <input
                      type="text"
                      value={newSessionVideoId}
                      onChange={(e) => setNewSessionVideoId(e.target.value)}
                      placeholder="ID Video Live hoặc ID Bài Viết trên Fanpage (VD: 123456_987654)"
                      className="w-full px-3 py-2 rounded-xl border border-indigo-300 bg-indigo-50/40 text-xs"
                    />
                  </>
                )}
                <button
                  type="submit"
                  className="w-full py-2 rounded-xl bg-indigo-600 text-white text-xs font-bold"
                >
                  + Mở Phiên Livestream Mới
                </button>
              </form>

              <div className="divide-y divide-slate-200 pt-2">
                {liveSessions.map((s) => {
                  const badge = getConnectionBadgeInfo(s.connection_mode);
                  return (
                    <div
                      key={s.id}
                      className="py-2.5 flex items-center justify-between text-xs"
                    >
                      <div>
                        <div className="font-bold text-slate-900">
                          {s.title}
                        </div>
                        <div className="text-slate-500">
                           Nguồn: {s.source_type} • Trạng thái: {s.status}
                        </div>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded border font-bold ${badge.className}`}
                      >
                        {badge.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: MESSENGER LOGS & MANUAL COPY/OPEN WORKFLOW */}
        {activeTab === "messages" && (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 divide-y divide-slate-200">
            <div className="p-4">
              <h2 className="font-extrabold text-sm text-slate-900">
                Lịch Sử Tin Nhắn Messenger & Hỗ Trợ Gửi Thủ Công
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Không bao giờ tự đánh dấu ĐÃ GỬI khi mới chỉ sao chép nội dung
                hoặc mở đường dẫn Messenger.
              </p>
            </div>
            {messages.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                Chưa có bản ghi tin nhắn nào.
              </div>
            ) : (
              messages.map((m) => (
                <div key={m.id} className="p-4 space-y-2 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded bg-slate-100 font-bold">
                        Chế độ: {m.provider_mode}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded font-bold ${
                          m.status === "SENT"
                            ? "bg-emerald-100 text-emerald-800"
                            : m.status === "NEEDS_MANUAL_ACTION"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-rose-100 text-rose-800"
                        }`}
                      >
                        {m.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          navigator.clipboard?.writeText(m.rendered_content);
                          notify(
                            "Đã sao chép nội dung tin nhắn (Trạng thái vẫn giữ nguyên cho tới khi bạn xác nhận đã gửi)."
                          );
                        }}
                        className="px-2.5 py-1 rounded-lg border border-slate-300 font-semibold hover:bg-slate-50"
                      >
                        📋 Sao chép nội dung
                      </button>
                      {m.messenger_thread_url && (
                        <a
                          href={m.messenger_thread_url}
                          target="_blank"
                          rel="noreferrer"
                          className="px-2.5 py-1 rounded-lg bg-blue-50 text-blue-700 border border-blue-200 font-semibold"
                        >
                          💬 Mở Messenger
                        </a>
                      )}
                    </div>
                  </div>
                  <pre className="p-3 rounded-xl bg-slate-50 border border-slate-200 whitespace-pre-wrap font-sans text-slate-800">
                    {m.rendered_content}
                  </pre>
                  {m.error_reason && (
                    <div className="text-amber-800 bg-amber-50 px-3 py-1.5 rounded-lg border border-amber-200">
                      <strong>Lý do:</strong> {m.error_reason}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* TAB 6: PRINT QUEUE */}
        {activeTab === "prints" && (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 divide-y divide-slate-200">
            <div className="p-4">
              <h2 className="font-extrabold text-sm text-slate-900">
                Hàng Đợi In Phiếu (80mm / A6 / A5)
              </h2>
            </div>
            {printJobs.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                Chưa có lệnh in nào trong hàng đợi.
              </div>
            ) : (
              printJobs.map((job) => (
                <div
                  key={job.id}
                  className="p-4 flex items-center justify-between text-xs"
                >
                  <div>
                    <div className="font-bold text-slate-900">
                      Job #{job.id.slice(0, 8)} • Khổ giấy: {job.paper_size} •
                      Chế độ: {job.print_mode}
                    </div>
                    <div className="text-slate-500 mt-0.5">
                      Trạng thái:{" "}
                      <strong className="text-indigo-700">{job.status}</strong>
                      {job.error_message ? ` (${job.error_message})` : ""}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      data-testid={`btn-preview-print-${job.id}`}
                      onClick={() => setPreviewPrintJob(job)}
                      className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white font-bold"
                    >
                      Xem Trước & In
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* TAB 7: PRINT & MESSAGE TEMPLATE CONFIGURATION */}
        {activeTab === "print_settings" && printSettings && (
          <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 space-y-4 text-xs">
            <h2 className="font-extrabold text-sm text-slate-900">
              Cấu Hình Mẫu In & Mẫu Tin Nhắn Messenger
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block font-bold mb-1">
                  Cỡ chữ phiếu in (px)
                </label>
                <input
                  type="number"
                  value={printSettings.font_size_px}
                  onChange={(e) =>
                    setPrintSettings({
                      ...printSettings,
                      font_size_px: Number(e.target.value),
                    })
                  }
                  className="w-full px-3 py-2 rounded-xl border border-slate-300"
                />
              </div>
              <div>
                <label className="block font-bold mb-1">Lề trang in (mm)</label>
                <input
                  type="number"
                  value={printSettings.margin_mm}
                  onChange={(e) =>
                    setPrintSettings({
                      ...printSettings,
                      margin_mm: Number(e.target.value),
                    })
                  }
                  className="w-full px-3 py-2 rounded-xl border border-slate-300"
                />
              </div>
              <div>
                <label className="block font-bold mb-1">Ghi chú cuối phiếu</label>
                <input
                  type="text"
                  value={printSettings.footer_note || ""}
                  onChange={(e) =>
                    setPrintSettings({
                      ...printSettings,
                      footer_note: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2 rounded-xl border border-slate-300"
                />
              </div>
            </div>
            <div>
              <label className="block font-bold mb-1">
                Mẫu tin nhắn xác nhận đơn hàng
              </label>
              <textarea
                rows={6}
                value={printSettings.messenger_template}
                onChange={(e) =>
                  setPrintSettings({
                    ...printSettings,
                    messenger_template: e.target.value,
                  })
                }
                className="w-full p-3 rounded-xl border border-slate-300 font-mono"
              />
            </div>
            <button
              type="button"
              onClick={async () => {
                if (!token || !activeShop) return;
                await apiFetch(
                  `/shops/${activeShop.id}/print-settings`,
                  {
                    method: "PUT",
                    body: JSON.stringify(printSettings),
                  },
                  token
                );
                notify("Đã lưu cấu hình mẫu in và tin nhắn!");
              }}
              className="px-5 py-2.5 rounded-xl bg-indigo-600 text-white font-bold"
            >
              Lưu Cấu Hình
            </button>
          </div>
        )}

        {/* TAB 8: STAFF & ROLES */}
        {activeTab === "members" && (
          <div className="space-y-4">
            <form
              onSubmit={handleAddMember}
              className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 grid grid-cols-1 sm:grid-cols-4 gap-2.5 text-xs"
            >
              <input
                type="email"
                required
                value={newMemberEmail}
                onChange={(e) => setNewMemberEmail(e.target.value)}
                placeholder="Email nhân viên"
                className="px-3 py-2 rounded-xl border border-slate-300"
              />
              <input
                type="text"
                value={newMemberName}
                onChange={(e) => setNewMemberName(e.target.value)}
                placeholder="Họ tên nhân viên"
                className="px-3 py-2 rounded-xl border border-slate-300"
              />
              <select
                value={newMemberRole}
                onChange={(e) => setNewMemberRole(e.target.value)}
                className="px-3 py-2 rounded-xl border border-slate-300 font-bold"
              >
                <option value="STAFF">STAFF (Nhân viên chốt đơn)</option>
                <option value="ADMIN">ADMIN (Quản trị viên)</option>
              </select>
              <button
                type="submit"
                className="px-4 py-2 rounded-xl bg-slate-900 text-white font-bold"
              >
                + Thêm Nhân Sự
              </button>
            </form>

            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 divide-y divide-slate-200 text-xs">
              {members.map((m) => (
                <div
                  key={m.id}
                  className="p-4 flex items-center justify-between"
                >
                  <div>
                    <div className="font-bold text-slate-900">{m.full_name}</div>
                    <div className="text-slate-500">{m.email}</div>
                  </div>
                  <span className="px-2.5 py-1 rounded bg-indigo-50 text-indigo-800 font-bold">
                    {m.role}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 9: AUDIT LOGS */}
        {activeTab === "audit" && (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 divide-y divide-slate-200 text-xs">
            <div className="p-4 font-extrabold text-sm">
              Nhật Ký Kiểm Toán Hệ Thống (Audit Logs)
            </div>
            {auditLogs.map((l) => (
              <div key={l.id} className="p-3.5 flex justify-between gap-2">
                <div>
                  <span className="font-bold text-indigo-700">{l.action}</span>{" "}
                  • <span>{l.entity_type}</span> ({l.entity_id.slice(0, 8)})
                  {l.details && (
                    <div className="text-slate-500 mt-0.5 font-mono">
                      {l.details}
                    </div>
                  )}
                </div>
                <div className="text-slate-400 whitespace-nowrap">
                  {new Date(l.created_at).toLocaleString("vi-VN")}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* TAB 10: SYSTEM HEALTH & META INTEGRATION DIAGNOSTICS */}
        {activeTab === "health" && (
          <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 space-y-4 text-xs">
            <h2 className="font-extrabold text-sm text-slate-900">
              Trạng Thái Sức Khỏe Hệ Thống & Kiểm Tra Tích Hợp Meta
            </h2>
            {healthInfo && (
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                <div>
                  <strong>Trạng thái Backend & DB:</strong>{" "}
                  <span className="text-emerald-700 font-bold uppercase">
                    {healthInfo.status}
                  </span>{" "}
                  ({healthInfo.database_dialect})
                </div>
                <div>
                  <strong>Môi trường (APP_ENV):</strong> {healthInfo.app_env}
                </div>
                <div>
                  <strong>Chế độ Meta hiện hành:</strong>{" "}
                  <span className="font-bold text-amber-700">
                    {healthInfo.meta_integration_mode}
                  </span>
                </div>
              </div>
            )}
            {metaStatus && (
              <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 space-y-1.5">
                <div className="font-bold text-amber-900">
                  Báo cáo minh bạch tích hợp Meta Graph API ({metaStatus.api_version}):
                </div>
                <div>
                  • Trạng thái Real Messenger Integration:{" "}
                  <strong>{metaStatus.real_messenger_status}</strong>
                </div>
                <div>
                  • Chính sách Trang Cá Nhân: {metaStatus.personal_profile_policy}
                </div>
                <div>
                  • Quyền bắt buộc cho Fanpage:{" "}
                  <code>{metaStatus.required_permissions?.join(", ")}</code>
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* MODAL 1: CREATE SHOP */}
      {showCreateShopModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4">
            <h3 className="text-lg font-extrabold text-slate-900">
              Tạo Cửa Hàng Mới
            </h3>
            <form onSubmit={handleCreateShop} className="space-y-3 text-xs">
              <div>
                <label className="block font-bold mb-1">Tên Shop</label>
                <input
                  type="text"
                  required
                  data-testid="create-shop-name"
                  value={newShopName}
                  onChange={(e) => setNewShopName(e.target.value)}
                  placeholder="VD: Thời Trang Hằng Live"
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-300"
                />
              </div>
              <div>
                <label className="block font-bold mb-1">Số điện thoại</label>
                <input
                  type="text"
                  value={newShopPhone}
                  onChange={(e) => setNewShopPhone(e.target.value)}
                  placeholder="0909.123.456"
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-300"
                />
              </div>
              <div>
                <label className="block font-bold mb-1">Khổ giấy in mặc định</label>
                <select
                  value={newShopPaperSize}
                  onChange={(e) => setNewShopPaperSize(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-300 font-bold"
                >
                  <option value="80mm">80mm (Máy in nhiệt K80)</option>
                  <option value="A6">Khổ A6</option>
                  <option value="A5">Khổ A5</option>
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                {shops.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowCreateShopModal(false)}
                    className="px-4 py-2 rounded-xl border border-slate-300 font-bold"
                  >
                    Đóng
                  </button>
                )}
                <button
                  type="submit"
                  data-testid="create-shop-submit"
                  className="px-5 py-2 rounded-xl bg-indigo-600 text-white font-bold"
                >
                  Lưu & Kích Hoạt Shop
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: PRODUCT & PRICE CONFIRMATION BEFORE "ĐÃ CHỐT" */}
      {confirmModalComment && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div
            data-testid="confirm-order-modal"
            className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 text-xs"
          >
            <h3 className="text-base font-extrabold text-slate-900">
              Xác Nhận Sản Phẩm & Giá Trước Khi Chốt
            </h3>
            <div className="p-3 rounded-xl bg-slate-100 text-slate-800">
              <strong>{confirmModalComment.commenter_name}:</strong> “
              {confirmModalComment.raw_message}”
            </div>

            <div className="space-y-3">
              <div>
                <label className="block font-bold mb-1">Chọn Sản Phẩm</label>
                <select
                  data-testid="modal-select-product"
                  value={confirmProductCode}
                  onChange={(e) => setConfirmProductCode(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-300 font-bold"
                >
                  {products.map((p) => (
                    <option key={p.id} value={p.code}>
                      {p.code} - {p.name} ({formatVND(p.unit_price)})
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block font-bold mb-1">Số lượng</label>
                  <input
                    type="number"
                    min={1}
                    data-testid="modal-input-quantity"
                    value={confirmQuantity}
                    onChange={(e) =>
                      setConfirmQuantity(Math.max(1, Number(e.target.value)))
                    }
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 font-bold"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1">Màu sắc</label>
                  <input
                    type="text"
                    value={confirmColor}
                    onChange={(e) => setConfirmColor(e.target.value)}
                    placeholder="Đỏ / Trắng..."
                    className="w-full px-3 py-2 rounded-xl border border-slate-300"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1">Size</label>
                  <input
                    type="text"
                    value={confirmSize}
                    onChange={(e) => setConfirmSize(e.target.value)}
                    placeholder="S / M / L"
                    className="w-full px-3 py-2 rounded-xl border border-slate-300"
                  />
                </div>
              </div>

              {selectedModalProduct && (
                <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 flex justify-between items-center">
                  <span>Tạm tính theo bảng giá shop:</span>
                  <span className="text-base font-black text-emerald-700">
                    {formatVND(
                      selectedModalProduct.unit_price * confirmQuantity
                    )}
                  </span>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setConfirmModalComment(null)}
                className="px-4 py-2.5 rounded-xl border border-slate-300 font-bold"
              >
                Hủy
              </button>
              <button
                type="button"
                data-testid="modal-confirm-submit"
                onClick={() =>
                  executeConfirmOrder(confirmModalComment, {
                    product_code: confirmProductCode,
                    quantity: confirmQuantity,
                    color: confirmColor || undefined,
                    size: confirmSize || undefined,
                    notes: confirmNotes || undefined,
                    force_confirm_ambiguous: true,
                  })
                }
                className="px-5 py-2.5 rounded-xl bg-emerald-600 text-white font-black"
              >
                XÁC NHẬN ĐÃ CHỐT
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: COMMENT DETAIL */}
      {selectedComment && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-3 text-xs">
            <h3 className="text-base font-extrabold">Chi Tiết Bình Luận</h3>
            <div>
              <strong>ID Nền tảng:</strong> {selectedComment.external_comment_id}
            </div>
            <div>
              <strong>Khách hàng:</strong> {selectedComment.commenter_name} (
              {selectedComment.commenter_external_id || "N/A"})
            </div>
            <div>
              <strong>Nguồn:</strong> {selectedComment.source_type} (
              {selectedComment.connection_mode})
            </div>
            <div>
              <strong>Nội dung nguyên gốc:</strong> “
              {selectedComment.raw_message}”
            </div>
            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setSelectedComment(null)}
                className="px-4 py-2 rounded-xl bg-slate-900 text-white font-bold"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 4: ORDER DETAIL & CANCEL */}
      {selectedOrder && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-3 text-xs">
            <h3 className="text-base font-extrabold">
              Chi Tiết Đơn Hàng {selectedOrder.order_code}
            </h3>
            <div>
              <strong>Số thứ tự khách (STT):</strong> #
              {String(selectedOrder.customer_stt).padStart(2, "0")}
            </div>
            <div>
              <strong>Trạng thái đơn:</strong> {selectedOrder.status}
            </div>
            <div>
              <strong>Tổng tiền sản phẩm:</strong>{" "}
              {formatVND(selectedOrder.subtotal)}
            </div>
            <div className="flex justify-between pt-3">
              {selectedOrder.status !== "CANCELLED" && (
                <button
                  type="button"
                  onClick={async () => {
                    if (!token || !activeShop) return;
                    await apiFetch(
                      `/shops/${activeShop.id}/orders/${selectedOrder.id}/status`,
                      {
                        method: "PATCH",
                        body: JSON.stringify({
                          status: "CANCELLED",
                          notes: "Hủy theo yêu cầu",
                        }),
                      },
                      token
                    );
                    setSelectedOrder(null);
                    notify(`Đã hủy đơn ${selectedOrder.order_code}`);
                    await loadShopData();
                  }}
                  className="px-4 py-2 rounded-xl bg-rose-600 text-white font-bold"
                >
                  Hủy Đơn Hàng
                </button>
              )}
              <button
                type="button"
                onClick={() => setSelectedOrder(null)}
                className="px-4 py-2 rounded-xl bg-slate-900 text-white font-bold ml-auto"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 5: PRINT PREVIEW & HONEST STATUS TRACKING */}
      {previewPrintJob && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div
            data-testid="print-preview-modal"
            className="bg-white rounded-2xl max-w-lg w-full p-5 space-y-3 text-xs max-h-[90vh] flex flex-col"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-extrabold">
                Xem Trước Phiếu In ({previewPrintJob.paper_size}) • Trạng thái:{" "}
                <span className="text-indigo-700">{previewPrintJob.status}</span>
              </h3>
              <button
                type="button"
                onClick={() => setPreviewPrintJob(null)}
                className="text-slate-500 font-bold"
              >
                ✕
              </button>
            </div>

            <div className="border border-slate-300 rounded-xl p-3 bg-slate-50 overflow-y-auto flex-1">
              <div
                data-testid="receipt-preview-content"
                dangerouslySetInnerHTML={{
                  __html: previewPrintJob.rendered_html,
                }}
              />
            </div>

            <div className="p-2.5 rounded-xl bg-amber-50 border border-amber-200 text-[11px] text-amber-900">
              Lưu ý: Mở hộp thoại in của trình duyệt chỉ chuyển trạng thái sang{" "}
              <strong>PRINTING</strong>. Sau khi máy in thực sự in ra giấy, hãy
              bấm <strong>“Xác Nhận Đã In Xong”</strong>.
            </div>

            <div className="flex flex-wrap justify-end gap-2">
              <button
                type="button"
                onClick={() => handleOpenBrowserPrint(previewPrintJob)}
                className="px-4 py-2 rounded-xl bg-indigo-600 text-white font-bold"
              >
                🖨 Mở Hộp Thoại In Trình Duyệt
              </button>
              <button
                type="button"
                data-testid="btn-confirm-printed"
                onClick={() =>
                  handleUpdatePrintStatus(previewPrintJob.id, "PRINTED")
                }
                className="px-4 py-2 rounded-xl bg-emerald-600 text-white font-bold"
              >
                ✓ Xác Nhận Đã In Xong
              </button>
              <button
                type="button"
                onClick={() =>
                  handleUpdatePrintStatus(previewPrintJob.id, "FAILED")
                }
                className="px-3 py-2 rounded-xl bg-rose-100 text-rose-800 font-bold"
              >
                Báo Lỗi Máy In
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
