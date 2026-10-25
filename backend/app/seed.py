from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    ConnectedAccount,
    ConnectionStatus,
    LiveSession,
    LiveSessionStatus,
    NotificationSetting,
    Product,
    ProductVariant,
    Shop,
    ShopMember,
    ShopRole,
    SourcePlatform,
    User,
)
from app.api.v1.router import _ingest_single_comment


def run_seed() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    if settings.is_production:
        print("ERROR: Không được chạy seed dữ liệu mẫu trong môi trường PRODUCTION.", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        owner = db.query(User).filter(User.email == "owner@chotlive.vn").first()
        if not owner:
            owner = User(
                email="owner@chotlive.vn",
                full_name="Nguyễn Thu Hằng (Chủ Shop)",
                hashed_password=hash_password("ChotLive@2026"),
                is_active=True,
            )
            db.add(owner)
            db.flush()

        staff = db.query(User).filter(User.email == "staff@chotlive.vn").first()
        if not staff:
            staff = User(
                email="staff@chotlive.vn",
                full_name="Trần Minh Tâm (Nhân Viên Chốt Đơn)",
                hashed_password=hash_password("ChotLive@2026"),
                is_active=True,
            )
            db.add(staff)
            db.flush()

        shop = db.query(Shop).filter(Shop.slug == "hang-fashion-live").first()
        if not shop:
            shop = Shop(
                name="Hằng Fashion Live",
                slug="hang-fashion-live",
                phone="0909.123.456",
                address="128 Nguyễn Trãi, Quận 1, TP. Hồ Chí Minh",
                stt_reset_rule="DAILY",
                print_paper_size="80mm",
                auto_print_on_confirm=True,
                confirm_before_print=True,
                inventory_enabled=False,
            )
            db.add(shop)
            db.flush()

            db.add(ShopMember(shop_id=shop.id, user_id=owner.id, role=ShopRole.OWNER.value, is_active=True))
            db.add(ShopMember(shop_id=shop.id, user_id=staff.id, role=ShopRole.STAFF.value, is_active=True))
            db.add(NotificationSetting(shop_id=shop.id))
            db.flush()

        # Connected accounts (Clearly labeled DEMO and MANUAL_MODE)
        demo_page = (
            db.query(ConnectedAccount)
            .filter(ConnectedAccount.shop_id == shop.id, ConnectedAccount.external_id == "demo_page_1001")
            .first()
        )
        if not demo_page:
            demo_page = ConnectedAccount(
                shop_id=shop.id,
                platform=SourcePlatform.DEMO.value,
                external_id="demo_page_1001",
                name="[DEMO] Fanpage Hằng Fashion Official",
                connection_status=ConnectionStatus.DEMO.value,
                granted_permissions="pages_show_list,pages_read_engagement,pages_messaging",
                missing_permissions=None,
            )
            db.add(demo_page)

        personal_acc = (
            db.query(ConnectedAccount)
            .filter(ConnectedAccount.shop_id == shop.id, ConnectedAccount.external_id == "personal_hang_01")
            .first()
        )
        if not personal_acc:
            personal_acc = ConnectedAccount(
                shop_id=shop.id,
                platform=SourcePlatform.FACEBOOK_PERSONAL.value,
                external_id="personal_hang_01",
                name="FB Cá Nhân: Thu Hằng Nguyễn",
                connection_status=ConnectionStatus.MANUAL_MODE.value,
                last_error="Trang cá nhân hoạt động ở chế độ Nhập Thủ Công (MANUAL_MODE) hợp pháp.",
            )
            db.add(personal_acc)
        db.flush()

        # Products
        sample_products = [
            ("A50", "Áo Sơ Mi Lụa Hàn Quốc Cao Cấp", 185000.0, 120, ["Đỏ", "Trắng", "Đen"], ["S", "M", "L"]),
            ("B20", "Đầm Hoa Nhí Dự Tiệc Dáng Xòe", 260000.0, 80, ["Hồng", "Vàng"], ["M", "L"]),
            ("V12", "Chân Váy Xếp Ly Dáng Dài", 145000.0, 95, [], []),
            ("SET01", "Set Bộ Mặc Nhà Cotton Mát Lạnh", 199000.0, 60, ["Xanh", "Be"], ["Freesize"]),
        ]
        for code, name, price, stock, colors, sizes in sample_products:
            p = db.query(Product).filter(Product.shop_id == shop.id, Product.code == code).first()
            if not p:
                p = Product(
                    shop_id=shop.id,
                    code=code,
                    name=name,
                    unit_price=price,
                    stock_quantity=stock,
                    is_active=True,
                )
                db.add(p)
                db.flush()
                for c in colors:
                    for s in sizes or [None]:
                        db.add(
                            ProductVariant(
                                product_id=p.id,
                                shop_id=shop.id,
                                sku=f"{code}-{c or ''}-{s or ''}".strip("-"),
                                color=c,
                                size=s,
                                stock_quantity=25,
                                is_active=True,
                            )
                        )
        db.flush()

        # Live sessions
        live_demo = (
            db.query(LiveSession)
            .filter(LiveSession.shop_id == shop.id, LiveSession.external_video_id == "live_demo_oct24")
            .first()
        )
        if not live_demo:
            live_demo = LiveSession(
                shop_id=shop.id,
                connected_account_id=demo_page.id,
                external_video_id="live_demo_oct24",
                title="[DEMO] Xả Kho Thu Đông Tối Nay - Mã A50, B20, V12",
                source_type=SourcePlatform.DEMO.value,
                connection_mode=ConnectionStatus.DEMO.value,
                status=LiveSessionStatus.LIVE.value,
            )
            db.add(live_demo)

        live_personal = (
            db.query(LiveSession)
            .filter(LiveSession.shop_id == shop.id, LiveSession.external_video_id == "live_personal_oct24")
            .first()
        )
        if not live_personal:
            live_personal = LiveSession(
                shop_id=shop.id,
                connected_account_id=personal_acc.id,
                external_video_id="live_personal_oct24",
                title="[MANUAL] Live Trang Cá Nhân Thu Hằng",
                source_type=SourcePlatform.FACEBOOK_PERSONAL.value,
                connection_mode=ConnectionStatus.MANUAL_MODE.value,
                status=LiveSessionStatus.LIVE.value,
            )
            db.add(live_personal)
        db.flush()

        # Sample comments (Clearly under DEMO / MANUAL_MODE sessions)
        base_time = datetime.now(timezone.utc) - timedelta(minutes=25)
        sample_comments = [
            (live_demo, "cmt_seed_01", "fb_10001", "Chị Lan Anh", "Chốt 2 áo A50 màu đỏ size M", 1),
            (live_demo, "cmt_seed_02", "fb_10002", "Nguyễn Bích Ngọc", "Cho em một cái mã V12 nhé shop", 3),
            (live_demo, "cmt_seed_03", "fb_10003", "Trần Thanh Hương", "A50 lấy 3 màu trắng size L", 5),
            (live_demo, "cmt_seed_04", "fb_10004", "Lê Mai Phương", "Shop ơi mẫu A50 hay B20 đẹp hơn nhỉ?", 7),
            (live_personal, "cmt_seed_05", "fb_10005", "Phạm Kiều Trinh", "Mã B20 màu hồng size M chị chốt 1 cái", 9),
        ]
        for sess, cid, uid, cname, msg, offset_min in sample_comments:
            _ingest_single_comment(
                db=db,
                shop=shop,
                live_session=sess,
                commenter_name=cname,
                raw_message=msg,
                external_comment_id=cid,
                commenter_external_id=uid,
                commented_at=base_time + timedelta(minutes=offset_min),
                external_page_id="demo_page_1001" if sess == live_demo else None,
            )

        db.commit()
        print("Seed development data thành công!")
        print("  - Chủ shop: owner@chotlive.vn / ChotLive@2026")
        print("  - Nhân viên: staff@chotlive.vn / ChotLive@2026")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
