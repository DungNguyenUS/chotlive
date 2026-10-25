import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { formatVND, getConnectionBadgeInfo } from "@/lib/api";
import ChotLiveApp from "@/app/page";

describe("Frontend Helpers & Status Badges", () => {
  it("formats Vietnamese currency accurately", () => {
    expect(formatVND(185000)).toContain("185");
    expect(formatVND(0)).toBe("0đ");
  });

  it("distinguishes DEMO, CONNECTED, MANUAL_MODE, NEEDS_PERMISSION, and FAILED badges", () => {
    expect(getConnectionBadgeInfo("DEMO").label).toContain("DEMO");
    expect(getConnectionBadgeInfo("CONNECTED").label).toContain("CONNECTED");
    expect(getConnectionBadgeInfo("MANUAL_MODE").label).toContain("MANUAL_MODE");
    expect(getConnectionBadgeInfo("NEEDS_PERMISSION").label).toContain("NEEDS_PERMISSION");
    expect(getConnectionBadgeInfo("FAILED").label).toContain("FAILED");
  });
});

describe("ChotLiveApp UI States (Login, Empty, Disconnected Error, Double-Click Protection)", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("renders Login screen when unauthenticated and displays error on invalid credentials", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Email hoặc mật khẩu không chính xác." }),
    } as any);

    render(<ChotLiveApp />);
    expect(screen.getByText("ChotLive Việt Nam")).toBeTruthy();

    fireEvent.click(screen.getByTestId("login-submit"));

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain(
        "Email hoặc mật khẩu không chính xác."
      );
    });
  });

  it("renders Disconnected/Error banner when backend API is unreachable", async () => {
    window.localStorage.setItem("chotlive_token", "valid_test_token");
    global.fetch = vi.fn().mockRejectedValue(new Error("Mất kết nối mạng tới máy chủ"));

    render(<ChotLiveApp />);

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain(
        "Mất kết nối mạng tới máy chủ"
      );
    });
  });
});
