import logging
import re
from statistics import mean
from typing import Any

from layoutlm_service import analyze_document_layout
from ocr_service import extract_ocr_data


logger = logging.getLogger(__name__)


def _clean_value(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip(" :,-")


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
            r"(?:invoice\s*(?:number|no|#)|bill\s*(?:number|no|#)|inv\s*(?:number|no|#))\s*[:\-]?\s*([A-Z0-9\-\/]+)",
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
        if any(keyword in lower_line for keyword in address_keywords):
            candidates.append(clean_line)
        elif re.search(r"\d{5,6}", clean_line) and any(char.isalpha() for char in clean_line):
            candidates.append(clean_line)
        if len(candidates) == 2:
            break

    return ", ".join(candidates)


def build_extracted_fields(raw_text: str, lines: list[str]) -> dict[str, str]:
    return {
        "invoice_number": extract_invoice_number(raw_text) or "Not found",
        "invoice_date": extract_invoice_date(raw_text) or "Not found",
        "vendor_name": extract_vendor_name(raw_text, lines) or "Not found",
        "total_amount": extract_total_amount(raw_text) or "Not found",
        "tax_amount": extract_tax_amount(raw_text) or "Not found",
        "address": extract_address(lines) or "Not found",
        "phone_number": extract_phone_number(raw_text) or "Not found",
    }


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
    raw_text = ocr_result["raw_text"]
    if not raw_text.strip():
        raise ValueError("OCR did not detect any readable text in the uploaded document.")

    layoutlm_result = analyze_document_layout(
        image=ocr_result["image"],
        words=ocr_result["words"],
        boxes=ocr_result["boxes"],
        raw_text=raw_text,
    )

    extracted_data = build_extracted_fields(raw_text, [entry["text"] for entry in ocr_result["entries"]])
    confidence_note = build_confidence_note(
        ocr_confidences=ocr_result["confidences"],
        layoutlm_note=layoutlm_result["note"],
    )

    logger.info("Hybrid extraction completed for %s", original_filename)
    return {
        "document_type": layoutlm_result["document_type"],
        "extracted_data": extracted_data,
        "raw_text": raw_text,
        "image_size": ocr_result["image_size"],
        "ocr_layout_data": {
            "full_text": raw_text,
            "words": ocr_result["words"],
            "bounding_boxes": ocr_result["bounding_boxes"],
            "normalized_boxes": ocr_result["normalized_boxes"],
        },
        "confidence_note": confidence_note,
        "layoutlm_summary": {
            "model_name": layoutlm_result["model_name"],
            "token_count": layoutlm_result["token_count"],
            "embedding_preview": layoutlm_result["embedding_preview"],
            "note": layoutlm_result["note"],
        },
    }
