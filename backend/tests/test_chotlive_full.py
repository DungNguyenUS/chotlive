from __future__ import annotations

import hashlib
import hmac
import io
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api.deps import reset_rate_limiter
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models import (
    Comment,
    MessageLog,
    MessageStatus,
    Order,
    OrderStatus,
    PrintJob,
    PrintJobStatus,
    Product,
)
from app.services.comment_parser import parse_livestream_comment


@pytest.fixture()
def test_db(tmp_path):
    db_file = tmp_path / "test_chotlive.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    reset_rate_limiter()
    yield TestingSessionLocal
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture()
def client(test_db):
    return TestClient(app)


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# A. DATABASE, PARSER & CORE BUSINESS LOGIC TESTS
# ==============================================================================

def test_comment_parser_vietnamese_patterns():
    p_a50 = Product(id="p1", shop_id="s1", code="A50", name="Áo Lụa A50", unit_price=185000.0, is_active=True)
    p_b20 = Product(id="p2", shop_id="s1", code="B20", name="Đầm Hoa B20", unit_price=260000.0, is_active=True)
    catalog = [p_a50, p_b20]

    # Case 1: "Mã A50 chị Hằng chốt"
    r1 = parse_livestream_comment("Mã A50 chị Hằng chốt", active_products=catalog)
    assert r1.product_code == "A50"
    assert r1.quantity == 1
    assert r1.has_buy_intent is True
    assert r1.is_ambiguous is False
    assert r1.matched_unit_price == 185000.0

    # Case 2: "Chốt 2 áo A50 màu đỏ size M"
    r2 = parse_livestream_comment("Chốt 2 áo A50 màu đỏ size M", active_products=catalog)
    assert r2.product_code == "A50"
    assert r2.quantity == 2
    assert r2.color == "Đỏ"
    assert r2.size == "M"
    assert r2.is_ambiguous is False

    # Case 3: "Cho em một cái mã B20"
    r3 = parse_livestream_comment("Cho em một cái mã B20", active_products=catalog)
    assert r3.product_code == "B20"
    assert r3.quantity == 1
    assert r3.matched_unit_price == 260000.0

    # Case 4: "A50 lấy 3"
    r4 = parse_livestream_comment("A50 lấy 3", active_products=catalog)
    assert r4.product_code == "A50"
    assert r4.quantity == 3
    assert r4.has_buy_intent is True

    # Case 5: Ambiguous (2 different codes in 1 comment)
    r5 = parse_livestream_comment("Shop ơi mẫu A50 hay B20 đẹp hơn?", active_products=catalog)
    assert r5.is_ambiguous is True
    assert len(r5.candidate_codes) == 2

    # Case 6: Non-existent code in catalog -> marked ambiguous
    r6 = parse_livestream_comment("Chốt 2 cái mã Z99", active_products=catalog)
    assert r6.product_code == "Z99"
    assert r6.is_ambiguous is True
    assert "valid_catalog_product" in r6.missing_fields


def test_full_order_workflow_and_anti_duplicate_concurrency(client: TestClient):
    # 1. Register Owner & Staff
    reg_owner = client.post(
        "/api/v1/auth/register",
        json={"email": "owner@test.vn", "full_name": "Chủ Shop", "password": "Password123"},
    )
    assert reg_owner.status_code == 201
    owner_token = reg_owner.json()["access_token"]

    # 2. Create Shop
    shop_res = client.post(
        "/api/v1/shops",
        headers=_auth_header(owner_token),
        json={"name": "Shop Thời Trang Việt", "stt_reset_rule": "DAILY", "print_paper_size": "80mm"},
    )
    assert shop_res.status_code == 201
    shop_id = shop_res.json()["id"]

    # 3. Add Staff member
    staff_res = client.post(
        f"/api/v1/shops/{shop_id}/members",
        headers=_auth_header(owner_token),
        json={
            "email": "staff@test.vn",
            "full_name": "Nhân Viên 1",
            "password": "Password123",
            "role": "STAFF",
        },
    )
    assert staff_res.status_code == 201

    login_staff = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.vn", "password": "Password123"},
    )
    staff_token = login_staff.json()["access_token"]

    # 4. Create Product A50
    prod_res = client.post(
        f"/api/v1/shops/{shop_id}/products",
        headers=_auth_header(owner_token),
        json={"code": "A50", "name": "Áo Sơ Mi Lụa", "unit_price": 150000.0, "stock_quantity": 50},
    )
    assert prod_res.status_code == 201
    product_id = prod_res.json()["id"]

    # 5. Create DEMO Live Session
    sess_res = client.post(
        f"/api/v1/shops/{shop_id}/live-sessions",
        headers=_auth_header(owner_token),
        json={"title": "Live Tối Thứ 7", "source_type": "DEMO"},
    )
    assert sess_res.status_code == 201
    session_id = sess_res.json()["id"]
    assert sess_res.json()["connection_mode"] == "DEMO"

    # 6. Receive Comment keeping exact raw_message
    raw_text = "Chốt 2 áo A50 màu đỏ size M nhé shop ơi!!!"
    cmt_res = client.post(
        f"/api/v1/shops/{shop_id}/comments",
        headers=_auth_header(owner_token),
        json={
            "live_session_id": session_id,
            "commenter_name": "Chị Hằng",
            "commenter_external_id": "fb_user_999",
            "raw_message": raw_text,
            "external_comment_id": "ext_cmt_001",
        },
    )
    assert cmt_res.status_code == 201
    comment_id = cmt_res.json()["id"]
    assert cmt_res.json()["raw_message"] == raw_text
    assert cmt_res.json()["parsed_product_code"] == "A50"
    assert cmt_res.json()["parsed_quantity"] == 2

    # 7. Staff 1 confirms order ("ĐÃ CHỐT")
    confirm1 = client.post(
        f"/api/v1/shops/{shop_id}/orders/confirm",
        headers=_auth_header(owner_token),
        json={
            "comment_id": comment_id,
            "idempotency_key": "idem_key_staff_1",
        },
    )
    assert confirm1.status_code == 201
    data1 = confirm1.json()
    assert data1["was_idempotent_replay"] is False
    order1 = data1["order"]
    assert order1["subtotal"] == 300000.0  # 2 * 150,000
    assert order1["customer_stt"] == 1
    assert order1["order_code"].startswith("DH-")
    assert data1["message_log"]["status"] == "SENT"
    assert data1["message_log"]["provider_mode"] == "MOCK"
    assert data1["print_job"]["status"] == "QUEUED"

    # 8. Staff 2 clicks "ĐÃ CHỐT" on the SAME comment with a DIFFERENT idempotency_key
    # Must NOT create a second order!
    confirm2 = client.post(
        f"/api/v1/shops/{shop_id}/orders/confirm",
        headers=_auth_header(staff_token),
        json={
            "comment_id": comment_id,
            "idempotency_key": "idem_key_staff_2_concurrent",
        },
    )
    assert confirm2.status_code == 201
    data2 = confirm2.json()
    assert data2["was_idempotent_replay"] is True
    assert data2["order"]["id"] == order1["id"]

    # Verify total orders in DB for this shop is strictly 1
    orders_list = client.get(f"/api/v1/shops/{shop_id}/orders", headers=_auth_header(owner_token)).json()
    assert len(orders_list) == 1

    # 9. Verify price snapshot immutability: Changing Product price later must NOT alter existing order
    client.patch(
        f"/api/v1/shops/{shop_id}/products/{product_id}",
        headers=_auth_header(owner_token),
        json={"unit_price": 999000.0},
    )
    order_detail = client.get(
        f"/api/v1/shops/{shop_id}/orders/{order1['id']}",
        headers=_auth_header(owner_token),
    ).json()
    assert order_detail["subtotal"] == 300000.0
    assert order_detail["items"][0]["unit_price_snapshot"] == 150000.0

    # 10. Cancel order and verify dashboard excludes cancelled order revenue
    cancel_res = client.patch(
        f"/api/v1/shops/{shop_id}/orders/{order1['id']}/status",
        headers=_auth_header(owner_token),
        json={"status": "CANCELLED", "notes": "Khách xin đổi mẫu"},
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    dash = client.get(f"/api/v1/shops/{shop_id}/dashboard", headers=_auth_header(owner_token)).json()
    assert dash["total_orders"] == 1
    assert dash["cancelled_orders"] == 1
    assert dash["confirmed_revenue"] == 0.0
    assert dash["unique_confirmed_customers"] == 0


# ==============================================================================
# B. MESSENGER ADAPTER, RETRY, POLICY & PERSONAL PROFILE TESTS
# ==============================================================================

def test_messenger_policies_retry_and_personal_profile_manual_mode(client: TestClient):
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "msgtest@test.vn", "full_name": "Shop Msg", "password": "Password123"},
    )
    token = reg.json()["access_token"]
    shop_id = client.post(
        "/api/v1/shops",
        headers=_auth_header(token),
        json={"name": "Shop Messenger Test"},
    ).json()["id"]

    client.post(
        f"/api/v1/shops/{shop_id}/products",
        headers=_auth_header(token),
        json={"code": "B20", "name": "Đầm Dự Tiệc", "unit_price": 200000.0},
    )

    # 1. Personal Profile Live Session -> Must be MANUAL_MODE and message status NEEDS_MANUAL_ACTION
    personal_sess = client.post(
        f"/api/v1/shops/{shop_id}/live-sessions",
        headers=_auth_header(token),
        json={"title": "Live Cá Nhân", "source_type": "FACEBOOK_PERSONAL"},
    ).json()
    assert personal_sess["connection_mode"] == "MANUAL_MODE"

    cmt_personal = client.post(
        f"/api/v1/shops/{shop_id}/comments",
        headers=_auth_header(token),
        json={
            "live_session_id": personal_sess["id"],
            "commenter_name": "Khách Cá Nhân",
            "commenter_external_id": "1000998877",
            "raw_message": "Chốt 1 B20",
        },
    ).json()

    ord_personal = client.post(
        f"/api/v1/shops/{shop_id}/orders/confirm",
        headers=_auth_header(token),
        json={"comment_id": cmt_personal["id"], "idempotency_key": "idem_personal_1"},
    ).json()

    msg_personal = ord_personal["message_log"]
    assert msg_personal["status"] == "NEEDS_MANUAL_ACTION"
    assert msg_personal["provider_mode"] == "MANUAL"
    assert "Chào chị Khách Cá Nhân!" in msg_personal["rendered_content"]
    assert "200.000đ" in msg_personal["rendered_content"]
    assert msg_personal["messenger_thread_url"] == "https://www.facebook.com/messages/t/1000998877"

    # 2. DEMO Session with Simulated Ambiguous Write Timeout -> Must NOT retry and must be NEEDS_MANUAL_ACTION
    demo_sess = client.post(
        f"/api/v1/shops/{shop_id}/live-sessions",
        headers=_auth_header(token),
        json={"title": "Live Demo", "source_type": "DEMO"},
    ).json()

    cmt_timeout = client.post(
        f"/api/v1/shops/{shop_id}/comments",
        headers=_auth_header(token),
        json={
            "live_session_id": demo_sess["id"],
            "commenter_name": "Khách Timeout",
            "external_comment_id": "SIMULATE_AMBIGUOUS_TIMEOUT_01",
            "raw_message": "Chốt 1 B20",
        },
    ).json()

    ord_timeout = client.post(
        f"/api/v1/shops/{shop_id}/orders/confirm",
        headers=_auth_header(token),
        json={"comment_id": cmt_timeout["id"], "idempotency_key": "idem_timeout_1"},
    ).json()

    assert ord_timeout["message_log"]["status"] == "NEEDS_MANUAL_ACTION"
    assert ord_timeout["message_log"]["retry_count"] == 0
    assert ord_timeout["message_log"]["error_code"] == "AMBIGUOUS_WRITE_TIMEOUT"

    # 3. Simulated Transient 503 -> Retries up to max_retries (3) then marks FAILED
    cmt_503 = client.post(
        f"/api/v1/shops/{shop_id}/comments",
        headers=_auth_header(token),
        json={
            "live_session_id": demo_sess["id"],
            "commenter_name": "Khách 503",
            "external_comment_id": "SIMULATE_TRANSIENT_503_01",
            "raw_message": "Chốt 1 B20",
        },
    ).json()

    ord_503 = client.post(
        f"/api/v1/shops/{shop_id}/orders/confirm",
        headers=_auth_header(token),
        json={"comment_id": cmt_503["id"], "idempotency_key": "idem_503_1"},
    ).json()

    assert ord_503["message_log"]["status"] == "FAILED"
    assert ord_503["message_log"]["retry_count"] == 3

    # 4. Comment older than 7 days -> Blocked by Meta 7-day Private Reply policy
    old_date = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    cmt_old = client.post(
        f"/api/v1/shops/{shop_id}/comments",
        headers=_auth_header(token),
        json={
            "live_session_id": demo_sess["id"],
            "commenter_name": "Khách Quá Hạn 7 Ngày",
            "external_comment_id": "cmt_expired_8d",
            "raw_message": "Chốt 1 B20",
            "commented_at": old_date,
        },
    ).json()

    ord_old = client.post(
        f"/api/v1/shops/{shop_id}/orders/confirm",
        headers=_auth_header(token),
        json={"comment_id": cmt_old["id"], "idempotency_key": "idem_old_1"},
    ).json()

    assert ord_old["message_log"]["status"] == "NEEDS_MANUAL_ACTION"
    assert ord_old["message_log"]["error_code"] == "PRIVATE_REPLY_WINDOW_EXPIRED_7D"


# ==============================================================================
# C. PRINTING TESTS (VIETNAMESE, PAPER SIZES, PRINT BRIDGE FAILURE, REPRINT)
# ==============================================================================

def test_printing_vietnamese_paper_sizes_and_bridge_failure_resilience(client: TestClient):
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "print@test.vn", "full_name": "Shop Print", "password": "Password123"},
    )
    token = reg.json()["access_token"]
    shop_id = client.post(
        "/api/v1/shops",
        headers=_auth_header(token),
        json={"name": "Shop In Phiếu Chuẩn Việt", "print_paper_size": "80mm"},
    ).json()["id"]

    client.post(
        f"/api/v1/shops/{shop_id}/products",
        headers=_auth_header(token),
        json={"code": "V12", "name": "Chân Váy Xếp Ly Dáng Dài", "unit_price": 145000.0},
    )
    sess_id = client.post(
        f"/api/v1/shops/{shop_id}/live-sessions",
        headers=_auth_header(token),
        json={"title": "Live In Phiếu", "source_type": "DEMO"},
    ).json()["id"]

    long_comment = (
        "Chốt 3 cái mã V12 màu đen size L nhé shop ơi, nhớ kiểm tra kỹ đường may giúp chị "
        "vì chị mua tặng sinh nhật bạn thân ở Hà Nội!"
    )
    cmt_id = client.post(
        f"/api/v1/shops/{shop_id}/comments",
        headers=_auth_header(token),
        json={
            "live_session_id": sess_id,
            "commenter_name": "Nguyễn Thị Phương Thảo",
            "raw_message": long_comment,
        },
    ).json()["id"]

    # Confirm order using PRINT_BRIDGE (which is not running on port 9100 -> must FAIL print job but KEEP order!)
    res = client.post(
        f"/api/v1/shops/{shop_id}/orders/confirm",
        headers=_auth_header(token),
        json={
            "comment_id": cmt_id,
            "idempotency_key": "idem_print_bridge_fail",
            "print_mode": "PRINT_BRIDGE",
        },
    )
    assert res.status_code == 201
    body = res.json()
    order_id = body["order"]["id"]
    assert body["order"]["status"] == "CONFIRMED"
    assert body["print_job"]["status"] == "FAILED"
    assert "Local Print Bridge" in body["print_job"]["error_message"]

    # Reprint in A6 and A5 via Browser mode -> must succeed and contain Vietnamese text & all required fields
    reprint_a6 = client.post(
        f"/api/v1/shops/{shop_id}/orders/{order_id}/reprint?paper_size=A6&print_mode=BROWSER",
        headers=_auth_header(token),
    )
    assert reprint_a6.status_code == 200
    job_a6 = reprint_a6.json()
    assert job_a6["paper_size"] == "A6"
    assert job_a6["status"] == "QUEUED"
    html_a6 = job_a6["rendered_html"]
    assert "PHIẾU CHỐT ĐƠN LIVESTREAM" in html_a6
    assert "Nguyễn Thị Phương Thảo" in html_a6
    assert "Chân Váy Xếp Ly Dáng Dài" in html_a6
    assert "435.000đ" in html_a6
    assert "105mm" in html_a6


# ==============================================================================
# E. SECURITY, CROSS-SHOP ISOLATION, WEBHOOK SIGNATURE & RATE LIMITING
# ==============================================================================

def test_security_cross_shop_isolation_webhook_signature_and_rate_limit(client: TestClient):
    # Shop A Owner
    t_a = client.post(
        "/api/v1/auth/register",
        json={"email": "shopa@test.vn", "full_name": "Owner A", "password": "Password123"},
    ).json()["access_token"]
    shop_a = client.post("/api/v1/shops", headers=_auth_header(t_a), json={"name": "Shop A"}).json()["id"]

    # Shop B Owner
    t_b = client.post(
        "/api/v1/auth/register",
        json={"email": "shopb@test.vn", "full_name": "Owner B", "password": "Password123"},
    ).json()["access_token"]
    shop_b = client.post("/api/v1/shops", headers=_auth_header(t_b), json={"name": "Shop B"}).json()["id"]

    # 1. Cross-shop access from User B to Shop A must return 403 Forbidden
    cross_res = client.get(f"/api/v1/shops/{shop_a}/orders", headers=_auth_header(t_b))
    assert cross_res.status_code == 403

    # 2. Unauthenticated access must return 401 Unauthorized
    unauth_res = client.get(f"/api/v1/shops/{shop_a}/orders")
    assert unauth_res.status_code == 401

    # 3. Negative product price must return 422 Validation Error
    neg_price = client.post(
        f"/api/v1/shops/{shop_a}/products",
        headers=_auth_header(t_a),
        json={"code": "BAD", "name": "Giá Âm", "unit_price": -50000},
    )
    assert neg_price.status_code == 422

    # 4. Webhook signature verification & duplicate webhook idempotency
    client.post(
        f"/api/v1/shops/{shop_a}/connected-accounts",
        headers=_auth_header(t_a),
        json={
            "platform": "FACEBOOK_PAGE",
            "external_id": "page_999",
            "name": "Fanpage A",
            "access_token": "secret_page_token",
            "granted_permissions": ["pages_show_list", "pages_read_engagement", "pages_messaging"],
        },
    )
    client.post(
        f"/api/v1/shops/{shop_a}/live-sessions",
        headers=_auth_header(t_a),
        json={"title": "Live Fanpage", "source_type": "FACEBOOK_PAGE"},
    )

    webhook_payload = {
        "object": "page",
        "entry": [
            {
                "id": "page_999",
                "time": 1710000000,
                "changes": [
                    {
                        "field": "feed",
                        "value": {
                            "item": "comment",
                            "verb": "add",
                            "comment_id": "wh_cmt_1001",
                            "created_time": 1710000000,
                            "from": {"id": "psid_555", "name": "Khách Webhook"},
                            "message": "Chốt 2 áo A50",
                        },
                    }
                ],
            }
        ],
    }
    raw_bytes = json.dumps(webhook_payload).encode("utf-8")

    # Invalid signature -> 403
    bad_wh = client.post(
        "/api/v1/webhooks/meta",
        content=raw_bytes,
        headers={"X-Hub-Signature-256": "sha256=invalid_sig"},
    )
    assert bad_wh.status_code == 403

    # Valid signature -> 200 OK and ingests 1 comment
    secret = settings.META_APP_SECRET or "dev_webhook_secret"
    valid_sig = "sha256=" + hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

    ok_wh1 = client.post(
        "/api/v1/webhooks/meta",
        content=raw_bytes,
        headers={"X-Hub-Signature-256": valid_sig},
    )
    assert ok_wh1.status_code == 200
    assert ok_wh1.json()["ingested_comments"] == 1

    # Duplicate webhook delivery -> 200 OK and ignores duplicate
    ok_wh2 = client.post(
        "/api/v1/webhooks/meta",
        content=raw_bytes,
        headers={"X-Hub-Signature-256": valid_sig},
    )
    assert ok_wh2.status_code == 200
    assert ok_wh2.json()["ingested_comments"] == 0
    assert ok_wh2.json()["duplicate_events_ignored"] == 1

    # 5. Rate limiting check using X-Test-Rate-Limit header
    for _ in range(3):
        r = client.get("/api/v1/health", headers={"X-Test-Rate-Limit": "3"})
        assert r.status_code == 200
    r_blocked = client.get("/api/v1/health", headers={"X-Test-Rate-Limit": "3"})
    assert r_blocked.status_code == 429


def test_csv_import_export_and_staff_role_permissions(client: TestClient):
    owner_reg = client.post(
        "/api/v1/auth/register",
        json={"email": "csvowner@test.vn", "full_name": "CSV Owner", "password": "Password123"},
    ).json()
    owner_token = owner_reg["access_token"]

    shop_id = client.post(
        "/api/v1/shops",
        headers=_auth_header(owner_token),
        json={"name": "Shop CSV & RBAC"},
    ).json()["id"]

    # Add STAFF member
    client.post(
        f"/api/v1/shops/{shop_id}/members",
        headers=_auth_header(owner_token),
        json={"email": "staffonly@test.vn", "full_name": "Staff Only", "password": "Password123", "role": "STAFF"},
    )
    staff_token = client.post(
        "/api/v1/auth/login",
        json={"email": "staffonly@test.vn", "password": "Password123"},
    ).json()["access_token"]

    # STAFF trying to modify shop configuration or add members must be blocked (403 Forbidden)
    staff_update_shop = client.patch(
        f"/api/v1/shops/{shop_id}",
        headers=_auth_header(staff_token),
        json={"name": "Hack Name"},
    )
    assert staff_update_shop.status_code == 403

    staff_add_member = client.post(
        f"/api/v1/shops/{shop_id}/members",
        headers=_auth_header(staff_token),
        json={"email": "another@test.vn", "full_name": "Another", "role": "ADMIN"},
    )
    assert staff_add_member.status_code == 403

    # CSV Import with valid and invalid rows
    csv_content = (
        "code,name,unit_price,stock_quantity,description\n"
        "SP01,Áo Thun Cotton,120000,30,Hàng đẹp\n"
        "SP02,Quần Jeans Nữ,-50000,10,Giá âm lỗi\n"
        "SP03,Đầm Công Sở,310000,15,Hàng mới\n"
    )
    import_res = client.post(
        f"/api/v1/shops/{shop_id}/products/import/csv",
        headers=_auth_header(owner_token),
        files={"file": ("products.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert import_res.status_code == 200
    imp_data = import_res.json()
    assert imp_data["created"] == 2
    assert len(imp_data["errors"]) == 1
    assert "Dòng 3" in imp_data["errors"][0]

    # CSV Export
    export_res = client.get(
        f"/api/v1/shops/{shop_id}/products/export/csv",
        headers=_auth_header(owner_token),
    )
    assert export_res.status_code == 200
    assert "SP01" in export_res.text
    assert "SP03" in export_res.text

