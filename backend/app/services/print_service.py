from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Comment,
    Customer,
    Order,
    OrderItem,
    PrintJob,
    PrintJobStatus,
    Shop,
)
from app.services.meta_service import format_vnd


PAPER_WIDTH_MAP = {
    "80mm": "80mm",
    "A6": "105mm",
    "A5": "148mm",
}


def build_print_snapshot(
    shop: Shop,
    order: Order,
    customer: Customer,
    first_item: OrderItem,
    comment: Optional[Comment],
    paper_size: Optional[str] = None,
) -> Dict[str, Any]:
    now_local = order.confirmed_at or datetime.now(timezone.utc)
    font_family = "Inter, Arial, sans-serif"
    font_size_px = 13
    margin_mm = 4
    header_note = ""
    footer_note = "Cảm ơn quý khách đã mua hàng trên livestream!"

    if shop.notification_setting:
        font_family = shop.notification_setting.font_family
        font_size_px = shop.notification_setting.font_size_px
        margin_mm = shop.notification_setting.margin_mm
        header_note = shop.notification_setting.header_note or ""
        footer_note = shop.notification_setting.footer_note or footer_note

    return {
        "shop_name": shop.name,
        "shop_phone": shop.phone or "",
        "shop_address": shop.address or "",
        "shop_logo_url": shop.logo_url or "",
        "title": "PHIẾU CHỐT ĐƠN LIVESTREAM",
        "customer_stt": f"#{order.customer_stt:02d}",
        "confirmed_at_str": now_local.strftime("%d/%m/%Y %H:%M:%S"),
        "customer_name": customer.display_name,
        "raw_comment": comment.raw_message if comment else "(Tạo thủ công)",
        "order_code": order.order_code,
        "product_code": first_item.product_code_snapshot,
        "product_name": first_item.product_name_snapshot,
        "variant": first_item.variant_snapshot or "Mặc định",
        "quantity": first_item.quantity,
        "unit_price": first_item.unit_price_snapshot,
        "unit_price_formatted": format_vnd(first_item.unit_price_snapshot),
        "subtotal": order.subtotal,
        "subtotal_formatted": format_vnd(order.subtotal),
        "notes": order.notes or "",
        "paper_size": paper_size or shop.print_paper_size or "80mm",
        "font_family": font_family,
        "font_size_px": font_size_px,
        "margin_mm": margin_mm,
        "header_note": header_note,
        "footer_note": footer_note,
    }


def render_receipt_html(snapshot: Dict[str, Any]) -> str:
    paper_size = snapshot.get("paper_size", "80mm")
    width_css = PAPER_WIDTH_MAP.get(paper_size, "80mm")
    font_family = html.escape(str(snapshot.get("font_family", "Inter, Arial, sans-serif")))
    font_size_px = int(snapshot.get("font_size_px", 13))
    margin_mm = int(snapshot.get("margin_mm", 4))

    logo_html = ""
    if snapshot.get("shop_logo_url"):
        safe_logo = html.escape(str(snapshot["shop_logo_url"]))
        logo_html = f'<div style="text-align:center;margin-bottom:4px;"><img src="{safe_logo}" alt="Logo" style="max-height:42px;" /></div>'

    notes_html = ""
    if snapshot.get("notes"):
        notes_html = f'<div class="row"><strong>Ghi chú:</strong> <span>{html.escape(str(snapshot["notes"]))}</span></div>'

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8" />
<title>{html.escape(snapshot["title"])} - {html.escape(snapshot["order_code"])}</title>
<style>
  @page {{
    size: {width_css} auto;
    margin: {margin_mm}mm;
  }}
  body {{
    font-family: {font_family};
    font-size: {font_size_px}px;
    line-height: 1.45;
    color: #000;
    margin: 0;
    padding: {margin_mm}mm;
    width: {width_css};
    box-sizing: border-box;
    word-wrap: break-word;
    overflow-wrap: anywhere;
  }}
  .header {{
    text-align: center;
    border-bottom: 1px dashed #000;
    padding-bottom: 6px;
    margin-bottom: 8px;
  }}
  .shop-name {{
    font-size: 1.15em;
    font-weight: 800;
    text-transform: uppercase;
  }}
  .title {{
    font-size: 1.05em;
    font-weight: 700;
    margin-top: 4px;
  }}
  .stt-box {{
    display: inline-block;
    border: 2px solid #000;
    padding: 2px 10px;
    font-size: 1.5em;
    font-weight: 900;
    margin: 6px 0;
  }}
  .row {{
    margin: 4px 0;
  }}
  .comment-box {{
    background: #f5f5f5;
    border-left: 3px solid #000;
    padding: 4px 6px;
    margin: 6px 0;
    font-style: italic;
  }}
  .divider {{
    border-top: 1px dashed #000;
    margin: 6px 0;
  }}
  .total {{
    font-size: 1.2em;
    font-weight: 800;
    display: flex;
    justify-content: space-between;
  }}
  .footer {{
    text-align: center;
    font-size: 0.9em;
    margin-top: 10px;
  }}
</style>
</head>
<body>
  <div class="header">
    {logo_html}
    <div class="shop-name">{html.escape(snapshot["shop_name"])}</div>
    <div class="title">{html.escape(snapshot["title"])}</div>
    <div class="stt-box">STT: {html.escape(snapshot["customer_stt"])}</div>
    <div>Ngày giờ chốt: {html.escape(snapshot["confirmed_at_str"])}</div>
  </div>

  <div class="row"><strong>Khách hàng:</strong> {html.escape(snapshot["customer_name"])}</div>
  <div class="row"><strong>Mã đơn:</strong> {html.escape(snapshot["order_code"])}</div>
  <div class="comment-box">"{html.escape(snapshot["raw_comment"])}"</div>

  <div class="divider"></div>
  <div class="row"><strong>Mã SP:</strong> {html.escape(snapshot["product_code"])}</div>
  <div class="row"><strong>Tên SP:</strong> {html.escape(snapshot["product_name"])}</div>
  <div class="row"><strong>Biến thể:</strong> {html.escape(snapshot["variant"])}</div>
  <div class="row"><strong>Số lượng:</strong> {snapshot["quantity"]} x {html.escape(snapshot["unit_price_formatted"])}</div>

  <div class="divider"></div>
  <div class="total">
    <span>THÀNH TIỀN:</span>
    <span>{html.escape(snapshot["subtotal_formatted"])}</span>
  </div>
  {notes_html}
  <div class="divider"></div>
  <div class="footer">{html.escape(snapshot.get("footer_note") or "")}</div>
</body>
</html>"""


def create_and_dispatch_print_job(
    db: Session,
    shop: Shop,
    order: Order,
    customer: Customer,
    first_item: OrderItem,
    comment: Optional[Comment],
    print_mode: str = "BROWSER",
    paper_size: Optional[str] = None,
) -> PrintJob:
    """
    Creates a PrintJob with a full data snapshot so reprints remain 100% consistent.
    Printer errors NEVER rollback or invalidate the confirmed Order.
    Browser mode stays QUEUED (or PRINTING when opened) and never falsely claims PRINTED
    until confirmed by staff or confirmed by the Local Print Bridge.
    """
    chosen_size = paper_size or shop.print_paper_size or "80mm"
    snapshot = build_print_snapshot(
        shop=shop,
        order=order,
        customer=customer,
        first_item=first_item,
        comment=comment,
        paper_size=chosen_size,
    )
    html_doc = render_receipt_html(snapshot)

    job = PrintJob(
        shop_id=shop.id,
        order_id=order.id,
        print_mode=print_mode,
        paper_size=chosen_size,
        status=PrintJobStatus.QUEUED.value,
        snapshot_payload=json.dumps(snapshot, ensure_ascii=False),
        rendered_html=html_doc,
    )
    db.add(job)
    db.flush()

    if print_mode == "PRINT_BRIDGE":
        try:
            with httpx.Client(timeout=float(settings.PRINT_BRIDGE_TIMEOUT_SECONDS)) as client:
                resp = client.post(
                    f"{settings.PRINT_BRIDGE_URL.rstrip('/')}/print",
                    json={"job_id": job.id, "paper_size": chosen_size, "snapshot": snapshot, "html": html_doc},
                )
            if resp.status_code == 200:
                job.status = PrintJobStatus.PRINTED.value
                job.printed_at = datetime.now(timezone.utc)
            else:
                job.status = PrintJobStatus.FAILED.value
                job.error_message = f"Print Bridge trả về HTTP {resp.status_code}"
        except Exception as exc:
            job.status = PrintJobStatus.FAILED.value
            job.error_message = f"Không thể kết nối Local Print Bridge ({settings.PRINT_BRIDGE_URL}): {type(exc).__name__}"
        db.flush()

    return job
