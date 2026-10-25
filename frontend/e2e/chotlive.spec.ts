import { test, expect } from "@playwright/test";

test.describe("ChotLive Full End-to-End Acceptance Flow", () => {
  test("User logs in, creates shop, adds product, receives mock comment, clicks ĐÃ CHỐT, views mock message & print preview", async ({
    page,
  }) => {
    // 1. Visit Login Screen
    await page.goto("/");
    await expect(page.getByText("ChotLive Việt Nam")).toBeVisible();

    // 2. Log in with seeded Owner account
    await page.getByTestId("login-email").fill("owner@chotlive.vn");
    await page.getByTestId("login-password").fill("ChotLive@2026");
    await page.getByTestId("login-submit").click();

    // 3. Verify Dashboard & Comments loaded
    await expect(page.getByTestId("global-search-input")).toBeVisible();
    await expect(page.getByText("Hằng Fashion Live").first()).toBeVisible();

    // 4. Create a new Product (code: K99, price: 250000)
    await page.getByTestId("tab-products").click();
    const uniqueCode = `K${Math.floor(10 + Math.random() * 89)}`;
    await page.getByTestId("new-product-code").fill(uniqueCode);
    await page.getByTestId("new-product-name").fill(`Áo Khoác Dạ ${uniqueCode}`);
    await page.getByTestId("new-product-price").fill("250000");
    await page.getByTestId("new-product-submit").click();
    await expect(page.getByText(`Áo Khoác Dạ ${uniqueCode}`)).toBeVisible();

    // 5. Switch to Comments tab and input a new livestream comment
    await page.getByTestId("tab-comments").click();
    const customerName = "Chị Ngọc Bích E2E";
    const commentText = `Chốt 2 áo ${uniqueCode} màu đen size M nhé shop`;
    await page.getByTestId("manual-commenter-name").fill(customerName);
    await page.getByTestId("manual-comment-text").fill(commentText);
    await page.getByTestId("manual-comment-submit").click();

    await expect(page.getByText(customerName).first()).toBeVisible();
    await expect(page.getByText(`“${commentText}”`).first()).toBeVisible();

    // 6. Locate the specific card containing the new comment and click "ĐÃ CHỐT"
    const targetCard = page.locator("div", { hasText: `“${commentText}”` }).filter({ has: page.locator('button:has-text("ĐÃ CHỐT")') }).last();
    await expect(targetCard).toBeVisible();
    await targetCard.locator('button:has-text("ĐÃ CHỐT")').click();

    // 7. Verify Print Preview Modal opens automatically with Vietnamese receipt content & exact subtotal (2 * 250,000 = 500.000đ)
    const printModal = page.getByTestId("print-preview-modal");
    await expect(printModal).toBeVisible();
    await expect(page.getByTestId("receipt-preview-content")).toContainText(
      "PHIẾU CHỐT ĐƠN LIVESTREAM"
    );
    await expect(page.getByTestId("receipt-preview-content")).toContainText(
      customerName
    );
    await expect(page.getByTestId("receipt-preview-content")).toContainText(
      "500.000đ"
    );

    // Confirm Printed
    await page.getByTestId("btn-confirm-printed").click();
    await page.locator('button:has-text("✕")').click();

    // 8. Clear search and verify Messenger Log tab has the mock message with status SENT
    await page.getByTestId("global-search-input").fill("");
    await page.getByTestId("tab-messages").click();
    await expect(page.getByText(`Chào chị ${customerName}!`).first()).toBeVisible();
    await expect(page.getByText("SENT").first()).toBeVisible();
  });
});
