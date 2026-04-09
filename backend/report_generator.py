from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


NOT_DETECTED = "Not Detected"

HEADER_FIELD_LABELS = {
    "vendor_name": "Company Name",
    "invoice_number": "Invoice Number",
    "invoice_date": "Invoice Date",
    "phone_number": "Phone Number",
}

BODY_FIELD_LABELS = {
    "bill_to": "Bill To",
    "customer_name": "Customer Name",
    "address": "Address",
    "gst_number": "GST Number",
}

FOOTER_FIELD_LABELS = {
    "subtotal": "Subtotal",
    "tax_amount": "Tax",
    "total_amount": "Grand Total",
    "payment_mode": "Payment Mode",
}


def _normalize_scalar(value: Any) -> str:
    if value is None:
        return NOT_DETECTED
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        cleaned = " ".join(value.split()).strip(" :")
        if not cleaned or cleaned.lower() in {"not found", "none", "null", "n/a", "na"}:
            return NOT_DETECTED
        return cleaned
    return NOT_DETECTED


def _title_case_document_type(document_type: Any) -> str:
    normalized = _normalize_scalar(document_type)
    if normalized == NOT_DETECTED:
        return normalized
    return " ".join(part.capitalize() for part in normalized.replace("_", " ").split())


def _normalize_extracted_data(extracted_data: dict[str, Any]) -> dict[str, str]:
    normalized = {str(key).lower().strip(): _normalize_scalar(value) for key, value in extracted_data.items()}

    alias_map = {
        "company_name": "vendor_name",
        "supplier_name": "vendor_name",
        "seller_name": "vendor_name",
        "invoice_no": "invoice_number",
        "invoice_id": "invoice_number",
        "date": "invoice_date",
        "invoice_total": "total_amount",
        "grand_total": "total_amount",
        "tax": "tax_amount",
        "billing_address": "address",
        "customer_address": "address",
        "client_name": "customer_name",
        "buyer_name": "customer_name",
    }

    for source_key, target_key in alias_map.items():
        if target_key not in normalized and source_key in normalized:
            normalized[target_key] = normalized[source_key]

    return normalized


def _find_region(layout_regions: list[dict[str, Any]], section_name: str) -> dict[str, Any]:
    for region in layout_regions:
        if str(region.get("section", "")).lower() == section_name:
            return region
    return {}


def _find_detected_block(detected_blocks: list[dict[str, Any]], block_type: str) -> dict[str, Any]:
    for block in detected_blocks:
        if str(block.get("block_type", "")).lower() == block_type:
            return block
    return {}


def _extract_labeled_value(lines: list[str], keywords: tuple[str, ...]) -> str:
    for line in lines:
        lower_line = line.lower()
        if not any(keyword in lower_line for keyword in keywords):
            continue
        if ":" in line:
            _, value = line.split(":", 1)
            normalized = _normalize_scalar(value)
            if normalized != NOT_DETECTED:
                return normalized
        tokens = line.split()
        if len(tokens) > 1:
            normalized = _normalize_scalar(" ".join(tokens[1:]))
            if normalized != NOT_DETECTED:
                return normalized
    return NOT_DETECTED


def _build_section_fields(
    normalized_data: dict[str, str],
    section_lines: list[str],
    field_labels: dict[str, str],
) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []

    for key, label in field_labels.items():
        value = normalized_data.get(key, NOT_DETECTED)
        if value == NOT_DETECTED:
            if key == "gst_number":
                value = _extract_labeled_value(section_lines, ("gst",))
            elif key == "payment_mode":
                value = _extract_labeled_value(section_lines, ("payment", "mode", "upi", "cash", "card"))
            elif key == "subtotal":
                value = _extract_labeled_value(section_lines, ("subtotal",))
            elif key == "bill_to":
                value = _extract_labeled_value(section_lines, ("bill to",))
        fields.append((label, value))

    return fields


def _looks_like_table_line(line: str) -> bool:
    lower_line = line.lower()
    table_keywords = ("qty", "quantity", "amount", "rate", "price", "description", "item", "total")
    has_keyword = any(keyword in lower_line for keyword in table_keywords)
    has_digits = any(character.isdigit() for character in line)
    return has_keyword or has_digits


def _build_tabular_lines(
    normalized_data: dict[str, str],
    table_region_lines: list[str],
    detected_block_lines: list[str],
) -> list[str]:
    candidate_lines = [line.strip() for line in table_region_lines + detected_block_lines if line.strip()]
    filtered_lines = [line for line in candidate_lines if _looks_like_table_line(line)]

    cleaned_rows: list[str] = []
    for line in filtered_lines:
        lower_line = line.lower()
        if lower_line in {"item", "description", "qty", "amount"}:
            continue
        if line not in cleaned_rows:
            cleaned_rows.append(line)

    if cleaned_rows:
        return [f"Item {index} : {row}" for index, row in enumerate(cleaned_rows, start=1)]

    fallback_total = normalized_data.get("total_amount", NOT_DETECTED)
    if fallback_total != NOT_DETECTED:
        return [f"Item 1 : Amount summary only detected | Amount: {fallback_total}"]

    return [f"Item 1 : {NOT_DETECTED}"]


def _position_summary_lines(layout_regions: list[dict[str, Any]], detected_blocks: list[dict[str, Any]]) -> list[tuple[str, str]]:
    region_lookup = {str(region.get("section", "")).lower(): region for region in layout_regions}
    block_lookup = {str(block.get("block_type", "")).lower(): block for block in detected_blocks}

    header_text = _normalize_scalar(region_lookup.get("header", {}).get("description"))
    body_text = _normalize_scalar(region_lookup.get("body", {}).get("description"))
    footer_text = _normalize_scalar(region_lookup.get("footer", {}).get("description"))

    table_block = block_lookup.get("table_region", {})
    table_text = _normalize_scalar(table_block.get("content_text")) if table_block else NOT_DETECTED
    if table_text != NOT_DETECTED:
        table_text = "Item-wise purchase details detected"
    else:
        table_text = NOT_DETECTED

    return [
        ("Header", header_text),
        ("Body", body_text),
        ("Table", table_text),
        ("Footer", footer_text),
    ]


def _format_labeled_lines(items: list[tuple[str, str]]) -> list[str]:
    label_width = max(len(label) for label, _ in items) if items else 0
    return [f"{label.ljust(label_width)} : {_normalize_scalar(value)}" for label, value in items]


def generate_structured_report(layout_json_payload: dict[str, Any]) -> str:
    extracted_data = _normalize_extracted_data(layout_json_payload.get("extracted_data", {}))
    document_layout_analysis = layout_json_payload.get("document_layout_analysis", {})
    layout_regions = document_layout_analysis.get("layout_regions", [])
    detected_blocks = document_layout_analysis.get("detected_blocks", [])

    header_region = _find_region(layout_regions, "header")
    body_region = _find_region(layout_regions, "body")
    footer_region = _find_region(layout_regions, "footer")
    table_block = _find_detected_block(detected_blocks, "table_region")

    header_lines = [line.strip() for line in header_region.get("content_lines", []) if str(line).strip()]
    body_lines = [line.strip() for line in body_region.get("content_lines", []) if str(line).strip()]
    footer_lines = [line.strip() for line in footer_region.get("content_lines", []) if str(line).strip()]
    table_lines = [line.strip() for line in table_block.get("content_lines", []) if str(line).strip()]

    header_items = _build_section_fields(extracted_data, header_lines, HEADER_FIELD_LABELS)
    body_items = _build_section_fields(extracted_data, body_lines, BODY_FIELD_LABELS)
    footer_items = _build_section_fields(extracted_data, footer_lines, FOOTER_FIELD_LABELS)
    position_items = _position_summary_lines(layout_regions, detected_blocks)
    tabular_items = _build_tabular_lines(extracted_data, table_lines, [])

    report_lines = [
        "DOCUMENT ANALYSIS REPORT",
        "========================",
        "",
        f"File Name      : {_normalize_scalar(layout_json_payload.get('file_name'))}",
        f"Document Type  : {_title_case_document_type(layout_json_payload.get('document_type'))}",
        "",
        "1. HEADER SECTION",
        "-----------------",
        *_format_labeled_lines(header_items),
        "",
        "2. BODY SECTION",
        "---------------",
        *_format_labeled_lines(body_items),
        "",
        "3. TABULAR CONTENT",
        "------------------",
        *tabular_items,
        "",
        "4. FOOTER SECTION",
        "-----------------",
        *_format_labeled_lines(footer_items),
        "",
        "5. POSITION SUMMARY",
        "-------------------",
        *_format_labeled_lines(position_items),
    ]
    return "\n".join(report_lines).strip() + "\n"


def save_structured_report(report_text: str, output_dir: Path, base_filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in base_filename.strip()) or "document"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"{safe_name}_analysis_report_{timestamp}.txt"
    report_path.write_text(report_text, encoding="utf-8")
    return report_path
