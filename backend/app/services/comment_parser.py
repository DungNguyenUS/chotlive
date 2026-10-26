from __future__ import annotations

import re
from typing import Dict, List, Optional, Protocol

from app.models import Product
from app.schemas import CommentParseResult


class NlpParserAdapter(Protocol):
    """Optional pluggable NLP/LLM interface. System never requires paid AI APIs."""

    def extract(self, raw_message: str, catalog_codes: List[str]) -> Optional[CommentParseResult]:
        ...


VIETNAMESE_NUMBER_WORDS: Dict[str, int] = {
    "một": 1,
    "mot": 1,
    "hai": 2,
    "đôi": 2,
    "cặp": 2,
    "ba": 3,
    "bốn": 4,
    "bon": 4,
    "tư": 4,
    "năm": 5,
    "nam": 5,
    "sáu": 6,
    "sau": 6,
    "bảy": 7,
    "bay": 7,
    "tám": 8,
    "tam": 8,
    "chín": 9,
    "chin": 9,
    "mười": 10,
    "muoi": 10,
    "chục": 10,
}

BUY_INTENT_KEYWORDS = [
    "chốt",
    "chot",
    "lấy",
    "lay",
    "cho em",
    "cho chị",
    "cho chi",
    "cho mình",
    "cho anh",
    "đặt",
    "dat",
    "mua",
    "ok mã",
    "mã",
    "cái",
    "chiếc",
    "bộ",
    "set",
    "áo",
    "quần",
    "váy",
    "đầm",
]

COLOR_PATTERNS = [
    "đỏ",
    "xanh đen",
    "xanh rêu",
    "xanh dương",
    "xanh lá",
    "xanh",
    "trắng",
    "đen",
    "vàng",
    "hồng",
    "tím",
    "nâu",
    "be",
    "kem",
    "xám",
    "ghi",
    "cam",
]

SIZE_REGEX = re.compile(
    r"(?:\bsize\s*[:\-]?\s*([a-zA-Z0-9]{1,4})\b|\b(freesize|free\s*size|xxxl|xxl|xl|xs|s|m|l|2xl|3xl)\b)",
    re.IGNORECASE,
)

CODE_TOKEN_REGEX = re.compile(r"\b([A-Za-z]{1,4}\d{1,5}[A-Za-z0-9]{0,2})\b")


def parse_livestream_comment(
    raw_message: str,
    active_products: Optional[List[Product]] = None,
    nlp_adapter: Optional[NlpParserAdapter] = None,
) -> CommentParseResult:
    """
    Rule-based Vietnamese livestream order comment parser.
    Prioritizes explicit shop product catalog codes and Vietnamese purchase patterns.
    Never guesses unit prices (prices come strictly from the shop's active Product catalog).
    Marks ambiguous or unknown product codes clearly so staff must confirm.
    """
    text = (raw_message or "").strip()
    lower = text.lower()

    catalog_map: Dict[str, Product] = {}
    if active_products:
        for p in active_products:
            if p.is_active:
                catalog_map[p.code.upper()] = p

    # 1. Identify candidate product codes
    matched_catalog_codes: List[str] = []
    if catalog_map:
        for code in catalog_map.keys():
            pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(code)}(?![A-Za-z0-9])", re.IGNORECASE)
            if pattern.search(text):
                matched_catalog_codes.append(code)

    regex_candidates: List[str] = []
    for m in CODE_TOKEN_REGEX.finditer(text):
        token = m.group(1).upper()
        if token in {"2XL", "3XL", "4XL", "5XL"}:
            continue
        if token not in regex_candidates:
            regex_candidates.append(token)

    candidate_codes = matched_catalog_codes if matched_catalog_codes else regex_candidates

    # 1b. If customer wrote product name instead of code (e.g. "chốt 2 áo size M"), match against product names
    if not candidate_codes and active_products:
        for p in active_products:
            if not p.is_active or not p.name:
                continue
            pname_lower = p.name.strip().lower()
            if pname_lower and pname_lower in lower:
                candidate_codes.append(p.code.upper())
        if not candidate_codes:
            for p in active_products:
                if not p.is_active or not p.name:
                    continue
                words = [w for w in re.split(r"\s+", p.name.strip().lower()) if len(w) >= 2]
                if any(re.search(rf"\b{re.escape(w)}\b", lower) for w in words):
                    candidate_codes.append(p.code.upper())

    # 2. Extract color
    detected_color: Optional[str] = None
    color_explicit = re.search(
        r"\bmàu\s+([a-zA-ZàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđĐ]+(?:\s+[a-zA-ZàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđĐ]+)?)",
        lower,
    )
    if color_explicit:
        raw_c = color_explicit.group(1).strip()
        for c in COLOR_PATTERNS:
            if raw_c.startswith(c):
                detected_color = c.capitalize()
                break
        if not detected_color:
            detected_color = raw_c.split()[0].capitalize()
    else:
        for c in COLOR_PATTERNS:
            if re.search(rf"\b{re.escape(c)}\b", lower):
                detected_color = c.capitalize()
                break

    # 3. Extract size
    detected_size: Optional[str] = None
    size_match = SIZE_REGEX.search(text)
    if size_match:
        s_val = size_match.group(1) or size_match.group(2)
        if s_val:
            detected_size = s_val.upper().replace(" ", "")

    # 4. Extract quantity
    quantity = 1
    qty_found = False

    # Remove product codes from text copy so digits inside "A50" are never mistaken for quantity
    cleaned_for_qty = text
    for c in candidate_codes:
        cleaned_for_qty = re.sub(rf"(?<![A-Za-z0-9]){re.escape(c)}(?![A-Za-z0-9])", " __CODE__ ", cleaned_for_qty, flags=re.IGNORECASE)

    qty_patterns = [
        r"(?:lấy|chốt|mua|đặt|sl|số lượng)\s*[:\-]?\s*(\d{1,3})\b",
        r"\b(\d{1,3})\s*(?:cái|chiếc|áo|quần|váy|đầm|bộ|set|đôi|cặp|mã|__CODE__)\b",
        r"__CODE__\s*(?:lấy|chốt|sl|x|\*)?\s*(\d{1,3})\b",
    ]
    for pat in qty_patterns:
        m = re.search(pat, cleaned_for_qty, flags=re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 999:
                quantity = val
                qty_found = True
                break

    if not qty_found:
        for word, val in VIETNAMESE_NUMBER_WORDS.items():
            if re.search(rf"\b{re.escape(word)}\s+(?:cái|chiếc|áo|quần|váy|đầm|bộ|set|mã|__CODE__)\b", cleaned_for_qty.lower()):
                quantity = val
                qty_found = True
                break

    # 5. Determine purchase intent
    has_keyword_intent = any(k in lower for k in BUY_INTENT_KEYWORDS)
    has_buy_intent = bool(has_keyword_intent or (candidate_codes and qty_found))

    # 6. Resolve product & ambiguity
    selected_code: Optional[str] = None
    matched_product: Optional[Product] = None
    is_ambiguous = False
    missing_fields: List[str] = []

    if len(candidate_codes) == 0:
        missing_fields.append("product_code")
        is_ambiguous = True
    elif len(candidate_codes) > 1:
        selected_code = candidate_codes[0]
        is_ambiguous = True
        if selected_code in catalog_map:
            matched_product = catalog_map[selected_code]
    else:
        selected_code = candidate_codes[0]
        if catalog_map:
            if selected_code in catalog_map:
                matched_product = catalog_map[selected_code]
            else:
                is_ambiguous = True
                missing_fields.append("valid_catalog_product")

    # If product has variants with color/size, check if missing
    if matched_product and matched_product.variants:
        active_vars = [v for v in matched_product.variants if v.is_active]
        has_colors = any(v.color for v in active_vars)
        has_sizes = any(v.size for v in active_vars)
        if has_colors and not detected_color:
            missing_fields.append("color")
            is_ambiguous = True
        if has_sizes and not detected_size:
            missing_fields.append("size")
            is_ambiguous = True

    # Confidence calculation
    confidence = 0.2
    if selected_code:
        confidence += 0.35
    if matched_product:
        confidence += 0.25
    if has_buy_intent:
        confidence += 0.15
    if qty_found:
        confidence += 0.05
    if is_ambiguous:
        confidence = min(confidence, 0.65)
    confidence = round(min(1.0, confidence), 2)

    if nlp_adapter and is_ambiguous:
        nlp_res = nlp_adapter.extract(raw_message, list(catalog_map.keys()))
        if nlp_res:
            return nlp_res

    return CommentParseResult(
        product_code=selected_code,
        matched_product_id=matched_product.id if matched_product else None,
        matched_product_name=matched_product.name if matched_product else None,
        matched_unit_price=matched_product.unit_price if matched_product else None,
        quantity=quantity,
        color=detected_color,
        size=detected_size,
        has_buy_intent=has_buy_intent,
        confidence=confidence,
        missing_fields=missing_fields,
        is_ambiguous=is_ambiguous,
        candidate_codes=candidate_codes,
    )
