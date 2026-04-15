from __future__ import annotations

import re
from statistics import mean
from typing import Any
import logging

try:
    from .errors import technical_http_error
    from .layoutlm_service import analyze_document_layout
    from .ocr_service import extract_ocr_data
except ImportError:
    from errors import technical_http_error
    from layoutlm_service import analyze_document_layout
    from ocr_service import extract_ocr_data

logger = logging.getLogger(__name__)

EMPTY_FIELDS = {
    "invoice_number": "Not found",
    "invoice_date": "Not found",
    "vendor_name": "Not found",
    "customer_name": "Not found",
    "total_amount": "Not found",
    "subtotal": "Not found",
    "tax_amount": "Not found",
    "address": "Not found",
    "phone_number": "Not found",
    "gst_number": "Not found",
    "payment_mode": "Not found",
    "footer_details": "Not found",
    "item_names": [],
    "quantities": [],
    "unit_prices": [],
    "line_items": [],
}

KEY_FIELDS = ("vendor_name", "invoice_number", "invoice_date", "total_amount")
NOT_FOUND = "Not found"


def _clean_value(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip(" :,-")


def _is_missing_value(value: Any) -> bool:
    return value in {NOT_FOUND, "", None}


def _normalize_numeric_token(token: str) -> str:
    if not token:
        return token

    has_digit = any(char.isdigit() for char in token)
    if not has_digit:
        return token

    translation = str.maketrans({
        "O": "0",
        "o": "0",
        "I": "1",
        "l": "1",
        "S": "5",
    })
    return token.translate(translation)


def normalize_ocr_text(raw_text: str) -> str:
    normalized_lines: list[str] = []
    for raw_line in raw_text.splitlines():
        tokens = [_normalize_numeric_token(token) for token in raw_line.split()]
        line = " ".join(tokens)
        line = re.sub(r"\bInvoice\s+Na\b", "Invoice No", line, flags=re.IGNORECASE)
        line = re.sub(r"\bBill\s+Ta\b", "Bill To", line, flags=re.IGNORECASE)
        line = re.sub(r"\b1NV\b", "INV", line)
        line = re.sub(r"\bOty\b", "Qty", line, flags=re.IGNORECASE)
        line = re.sub(r"\bPate\b", "Rate", line, flags=re.IGNORECASE)
        line = re.sub(r"\bRcad\b", "Road", line, flags=re.IGNORECASE)
        normalized_lines.append(_clean_value(line))
    return "\n".join(line for line in normalized_lines if line)


def _search_patterns(text: str, patterns: list[str], flags: int = re.IGNORECASE) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            if match.lastindex:
                return _clean_value(match.group(1))
            return _clean_value(match.group(0))
    return ""


def extract_invoice_number(text: str) -> str:
    return _search_patterns(
        text,
        [
            r"(?:invoice\s*(?:number|no|na|nu|#)|bill\s*(?:number|no|na|#)|inv\s*(?:number|no|#))\s*[:\-]?\s*([A-Z0-9\-\/]+)",
            r"\b(INV[-\/]?\d{3,})\b",
        ],
    )


def extract_invoice_date(text: str) -> str:
    return _search_patterns(
        text,
        [
            r"(?:invoice\s*date|date)\s*[:\-]?\s*([0-3]?\d[\/\-][0-1]?\d[\/\-]\d{2,4})",
            r"(?:invoice\s*date|date)\s*[:\-]?\s*([A-Za-z]{3,9}\s+[0-3]?\d,?\s+\d{4})",
            r"\b([0-3]?\d[\/\-][0-1]?\d[\/\-]\d{2,4})\b",
            r"\b([A-Za-z]{3,9}\s+[0-3]?\d,?\s+\d{4})\b",
        ],
    )


def extract_total_amount(text: str) -> str:
    value = _search_patterns(
        text,
        [
            r"(?:grand\s*total|total\s*amount|amount\s*due|invoice\s*total|net\s*amount|balance\s*due)\s*[:\-]?\s*(?:rs\.?|inr|usd|\$)?\s*([\d,]+(?:\.\d{2})?)",
        ],
    )
    if value:
        return value

    amounts = re.findall(r"(?:rs\.?|inr|usd|\$)?\s*([\d,]+(?:\.\d{2})?)", text, re.IGNORECASE)
    return _clean_value(amounts[-1]) if amounts else ""


def extract_subtotal_amount(text: str) -> str:
    return _search_patterns(
        text,
        [
            r"(?:subtotal|sub total|taxable amount)\s*[:\-]?\s*(?:rs\.?|inr|usd|\$)?\s*([\d,]+(?:\.\d{2})?)",
        ],
    )


def extract_tax_amount(text: str) -> str:
    return _search_patterns(
        text,
        [
            r"(?:tax|vat|gst|cgst|sgst|igst)\s*[:\-]?\s*(?:rs\.?|inr|usd|\$)?\s*([\d,]+(?:\.\d{2})?)",
        ],
    )


def extract_phone_number(text: str) -> str:
    return _search_patterns(
        text,
        [
            r"(?:phone|mobile|tel|contact)\s*[:\-]?\s*((?:\+\d{1,3}[\s\-]?)?(?:\d[\s\-]?){8,15})",
            r"(\+?\d[\d\-\s]{8,15}\d)",
        ],
    )


def extract_customer_name(text: str, lines: list[str]) -> str:
    labeled_value = _search_patterns(
        text,
        [
            r"\b(?:bill\s*to|customer(?:\s*name)?|client|buyer)\b\s*[:\-]?\s*([A-Za-z0-9&.,'()\- ]{3,100})",
        ],
    )
    if labeled_value:
        return labeled_value

    for index, line in enumerate(lines):
        if "bill to" in line.lower() and index + 1 < len(lines):
            candidate = _clean_value(lines[index + 1])
            if candidate:
                return candidate

    for line in lines:
        clean_line = _clean_value(line)
        lower_line = clean_line.lower()
        if not clean_line:
            continue
        if any(keyword in lower_line for keyword in ("invoice", "date", "address", "phone", "gst", "total", "item")):
            continue
        if "company" in lower_line:
            continue
        if re.search(r"\d", clean_line):
            continue
        return clean_line
    return ""


def extract_gst_number(text: str) -> str:
    normalized = text.upper().replace(" ", "")
    match = re.search(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]\b", normalized)
    return match.group(0) if match else ""


def extract_payment_mode(text: str) -> str:
    return _search_patterns(
        text,
        [
            r"(?:payment\s*mode|payment\s*method|paid\s*via)\s*[:\-]?\s*([A-Za-z ]{3,40})",
            r"\b(upi|cash|card|bank transfer|net banking)\b",
        ],
    )


def extract_vendor_name(text: str, lines: list[str]) -> str:
    labeled_value = _search_patterns(
        text,
        [
            r"(?:vendor|supplier|seller|from|bill\s*from)\s*[:\-]?\s*([A-Za-z0-9&.,'()\- ]{3,80})",
        ],
    )
    if labeled_value:
        return labeled_value

    for line in lines[:5]:
        clean_line = _clean_value(line)
        if not clean_line:
            continue
        if any(keyword in clean_line.lower() for keyword in ["invoice", "bill to", "ship to", "date", "tax"]):
            continue
        if re.search(r"\d", clean_line) and len(clean_line.split()) <= 2:
            continue
        return clean_line
    return ""


def extract_address(lines: list[str]) -> str:
    address_keywords = ("street", "road", "lane", "avenue", "floor", "building", "city", "state", "zip", "address")
    candidates: list[str] = []

    for line in lines:
        clean_line = _clean_value(line)
        lower_line = clean_line.lower()
        if len(clean_line) < 8:
            continue
        if "phone" in lower_line:
            continue
        if any(keyword in lower_line for keyword in address_keywords):
            candidates.append(clean_line)
        elif re.search(r"\d{5,6}", clean_line) and any(char.isalpha() for char in clean_line):
            candidates.append(clean_line)
        if len(candidates) == 2:
            break

    return ", ".join(candidates)


def extract_footer_details(lines: list[str]) -> str:
    footer_candidates = []
    footer_keywords = ("thank", "terms", "bank", "account", "payment", "authorised", "authorized")
    for line in lines:
        lower_line = line.lower()
        if any(keyword in lower_line for keyword in footer_keywords):
            footer_candidates.append(_clean_value(line))
    return " | ".join(dict.fromkeys(footer_candidates))


def _line_has_total_keyword(line: str) -> bool:
    return any(keyword in line.lower() for keyword in ("subtotal", "tax", "gst", "cgst", "sgst", "igst", "grand total", "total"))


def _extract_amounts_from_line(line: str) -> list[float]:
    amount_strings = re.findall(r"[\d,]+(?:\.\d{2})?", line)
    amounts: list[float] = []
    for value in amount_strings:
        try:
            amounts.append(float(value.replace(",", "")))
        except ValueError:
            continue
    return amounts


def _format_amount(value: float) -> str:
    return f"{value:.2f}"


def extract_line_items(lines: list[str]) -> list[dict[str, str]]:
    table_header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "item" in line.lower() and ("description" in line.lower() or "amount" in line.lower())
        ),
        -1,
    )
    if table_header_index == -1:
        return []

    candidate_lines: list[str] = []
    for line in lines[table_header_index + 1:]:
        lower_line = line.lower()
        if any(keyword in lower_line for keyword in ("gst", "tax", "subtotal", "grand total", "balance due", "amount due")):
            break
        candidate_lines.append(line)

    items: list[dict[str, str]] = []
    for line in candidate_lines:
        cleaned_line = _clean_value(line)
        if not cleaned_line or _line_has_total_keyword(cleaned_line):
            continue

        amounts = _extract_amounts_from_line(cleaned_line)
        if not amounts:
            continue

        name = _clean_value(re.sub(r"[\d,]+(?:\.\d{2})?", " ", cleaned_line))
        name = re.sub(r"\s+", " ", name)
        if not name or name.lower() in {"invoice", "date", "phone"}:
            continue

        quantity = ""
        unit_price = ""
        amount = ""

        if len(amounts) >= 3:
            quantity = str(int(amounts[0])) if amounts[0].is_integer() else _format_amount(amounts[0])
            unit_price = _format_amount(amounts[1])
            amount = _format_amount(amounts[2])
        elif len(amounts) == 2:
            unit_price = _format_amount(amounts[0])
            amount = _format_amount(amounts[1])
            if amounts[0] > 0:
                inferred_quantity = amounts[1] / amounts[0]
                if abs(inferred_quantity - round(inferred_quantity)) < 0.05:
                    quantity = str(int(round(inferred_quantity)))
        else:
            amount = _format_amount(amounts[0])

        items.append(
            {
                "description": name,
                "quantity": quantity or NOT_FOUND,
                "unit_price": unit_price or NOT_FOUND,
                "amount": amount or NOT_FOUND,
            }
        )

    unique_items: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in items:
        signature = (item["description"], item["quantity"], item["unit_price"], item["amount"])
        if signature in seen:
            continue
        seen.add(signature)
        unique_items.append(item)
    return unique_items


def _derive_amount_fields(extracted_fields: dict[str, Any]) -> dict[str, Any]:
    line_items = extracted_fields.get("line_items", [])
    numeric_amounts: list[float] = []
    for item in line_items:
        amount_text = str(item.get("amount", NOT_FOUND))
        if amount_text == NOT_FOUND:
            continue
        try:
            numeric_amounts.append(float(amount_text.replace(",", "")))
        except ValueError:
            continue

    subtotal_value = extracted_fields.get("subtotal", NOT_FOUND)
    total_value = extracted_fields.get("total_amount", NOT_FOUND)
    tax_value = extracted_fields.get("tax_amount", NOT_FOUND)

    def parse_amount(raw_value: Any) -> float | None:
        if _is_missing_value(raw_value):
            return None
        try:
            return float(str(raw_value).replace(",", ""))
        except ValueError:
            return None

    subtotal = parse_amount(subtotal_value)
    total = parse_amount(total_value)
    tax = parse_amount(tax_value)

    if subtotal is None and numeric_amounts:
        subtotal = sum(numeric_amounts)
        extracted_fields["subtotal"] = _format_amount(subtotal)

    if total is None and subtotal is not None and tax is not None:
        total = subtotal + tax
        extracted_fields["total_amount"] = _format_amount(total)

    if total is not None and subtotal is not None and total < subtotal:
        if tax is not None:
            total = subtotal + tax
            extracted_fields["total_amount"] = _format_amount(total)
        else:
            extracted_fields["total_amount"] = _format_amount(subtotal)

    return extracted_fields


def build_extracted_fields(raw_text: str, lines: list[str]) -> dict[str, str]:
    line_items = extract_line_items(lines)
    item_names = [item["description"] for item in line_items]
    quantities = [item["quantity"] for item in line_items if item["quantity"] != NOT_FOUND]
    unit_prices = [item["unit_price"] for item in line_items if item["unit_price"] != NOT_FOUND]

    extracted_fields = {
        "invoice_number": extract_invoice_number(raw_text) or NOT_FOUND,
        "invoice_date": extract_invoice_date(raw_text) or NOT_FOUND,
        "vendor_name": extract_vendor_name(raw_text, lines) or NOT_FOUND,
        "customer_name": extract_customer_name(raw_text, lines) or NOT_FOUND,
        "total_amount": extract_total_amount(raw_text) or NOT_FOUND,
        "subtotal": extract_subtotal_amount(raw_text) or NOT_FOUND,
        "tax_amount": extract_tax_amount(raw_text) or NOT_FOUND,
        "address": extract_address(lines) or NOT_FOUND,
        "phone_number": extract_phone_number(raw_text) or NOT_FOUND,
        "gst_number": extract_gst_number(raw_text) or NOT_FOUND,
        "payment_mode": extract_payment_mode(raw_text) or NOT_FOUND,
        "footer_details": extract_footer_details(lines) or NOT_FOUND,
        "item_names": item_names,
        "quantities": quantities,
        "unit_prices": unit_prices,
        "line_items": line_items,
    }
    return _derive_amount_fields(extracted_fields)


def build_confidence_note(ocr_confidences: list[float], layoutlm_note: str) -> str:
    if ocr_confidences:
        average_confidence = round(mean(ocr_confidences) * 100, 2)
        return (
            f"Hybrid OCR + rule-based extraction with LayoutLMv3 support. "
            f"Average OCR confidence: {average_confidence}%. {layoutlm_note}"
        )
    return (
        "Hybrid OCR + rule-based extraction with LayoutLMv3 support. "
        f"OCR confidence was unavailable. {layoutlm_note}"
    )


def build_extraction_result(image_path, original_filename: str) -> dict[str, Any]:
    ocr_result = extract_ocr_data(str(image_path))
    raw_text = normalize_ocr_text(ocr_result["raw_text"])
    lines = [line for line in raw_text.splitlines() if line.strip()]

    if sum(character.isalnum() for character in raw_text) < 20 or len(lines) < 3:
        logger.error("OCR extraction failed for %s | raw_text=%s", original_filename, raw_text[:500] or "<empty>")
        raise technical_http_error("No readable invoice text found", status_code=422, error_code="ocr_extraction_failed")

    layoutlm_result = analyze_document_layout(
        image=ocr_result["image"],
        words=ocr_result["words"],
        boxes=ocr_result["boxes"],
        entries=ocr_result["entries"],
        raw_text=raw_text,
    )

    extracted_data = build_extracted_fields(raw_text, lines) if raw_text.strip() else dict(EMPTY_FIELDS)

    extracted_key_count = sum(1 for key in KEY_FIELDS if not _is_missing_value(extracted_data.get(key)))
    if extracted_key_count == 0:
        logger.error("Field mapping incomplete for %s | raw_text=%s", original_filename, raw_text[:500])
        raise technical_http_error("Field mapping incomplete", status_code=422, error_code="field_mapping_incomplete")

    confidence_note = build_confidence_note(
        ocr_confidences=ocr_result["confidences"],
        layoutlm_note=layoutlm_result["note"],
    )
    if ocr_result.get("note"):
        confidence_note = f"{confidence_note} {ocr_result['note']}"

    logger.info("Normalized OCR text for %s: %s", original_filename, raw_text[:1000])
    logger.info("Extracted invoice fields for %s: %s", original_filename, extracted_data)

    return {
        "document_type": layoutlm_result["document_type"],
        "extracted_data": extracted_data,
        "raw_text": raw_text,
        "image_size": ocr_result["image_size"],
        "ocr_layout_data": {
            "full_text": ocr_result["full_text"],
            "words": ocr_result["words"],
            "bounding_boxes": ocr_result["bounding_boxes"],
            "normalized_boxes": ocr_result["normalized_boxes"],
            "lines": lines,
        },
        "layoutlmv3_status": layoutlm_result["layoutlmv3_status"],
        "document_layout_analysis": layoutlm_result["document_layout_analysis"],
        "confidence_note": confidence_note,
        "layoutlm_summary": {
            "model_name": layoutlm_result["model_name"],
            "token_count": layoutlm_result["token_count"],
            "embedding_preview": layoutlm_result["embedding_preview"],
            "note": layoutlm_result["note"],
        },
    }
