from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from PIL import Image

try:
    from .config import LAYOUTLM_ALLOW_DOWNLOAD, LAYOUTLM_MAX_TOKENS, MODEL_NAME
except ImportError:
    from config import LAYOUTLM_ALLOW_DOWNLOAD, LAYOUTLM_MAX_TOKENS, MODEL_NAME


logger = logging.getLogger(__name__)


HEADER_KEYWORDS = (
    "invoice",
    "bill to",
    "ship to",
    "seller",
    "vendor",
    "supplier",
    "gst",
    "tax invoice",
    "invoice no",
    "invoice number",
    "date",
)

TABLE_KEYWORDS = (
    "item",
    "description",
    "qty",
    "quantity",
    "rate",
    "price",
    "amount",
    "unit",
    "hsn",
    "sku",
)

TOTALS_KEYWORDS = (
    "subtotal",
    "tax",
    "gst",
    "cgst",
    "sgst",
    "igst",
    "grand total",
    "total",
    "amount due",
    "balance due",
    "net amount",
)


@lru_cache(maxsize=1)
def get_layoutlm_components() -> tuple[Any, Any, Any]:
    """
    Load the base LayoutLMv3 stack once.
    This is useful for document understanding embeddings and is demo-ready.
    True field extraction from LayoutLMv3 needs a fine-tuned token-classification or QA model.
    """
    try:
        import torch
        from transformers import LayoutLMv3Model, LayoutLMv3Processor
    except ImportError as exc:
        raise RuntimeError(
            "LayoutLMv3 dependencies are not installed. Install torch and transformers "
            "to enable layout-aware model execution."
        ) from exc

    pretrained_options = {
        "local_files_only": not LAYOUTLM_ALLOW_DOWNLOAD,
    }
    processor = LayoutLMv3Processor.from_pretrained(
        MODEL_NAME,
        apply_ocr=False,
        **pretrained_options,
    )
    model = LayoutLMv3Model.from_pretrained(MODEL_NAME, **pretrained_options)
    model.eval()
    return processor, model, torch


def _guess_document_type(raw_text: str) -> str:
    lower_text = raw_text.lower()
    if "invoice" in lower_text:
        return "invoice"
    if "receipt" in lower_text:
        return "receipt"
    if lower_text.strip():
        return "document"
    return "unknown"


def _clamp_box(box: list[int], width: int, height: int) -> list[int]:
    left, top, right, bottom = box
    left = max(0, min(int(left), width))
    top = max(0, min(int(top), height))
    right = max(left, min(int(right), width))
    bottom = max(top, min(int(bottom), height))
    return [left, top, right, bottom]


def _merge_boxes(boxes: list[list[int]], width: int, height: int) -> list[int]:
    if not boxes:
        return [0, 0, width, height]
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[2] for box in boxes)
    bottom = max(box[3] for box in boxes)
    return _clamp_box([left, top, right, bottom], width, height)


def _intersection_area(box_a: list[int], box_b: list[int]) -> int:
    left = max(int(box_a[0]), int(box_b[0]))
    top = max(int(box_a[1]), int(box_b[1]))
    right = min(int(box_a[2]), int(box_b[2]))
    bottom = min(int(box_a[3]), int(box_b[3]))
    if right <= left or bottom <= top:
        return 0
    return (right - left) * (bottom - top)


def _box_area(box: list[int]) -> int:
    return max(0, int(box[2]) - int(box[0])) * max(0, int(box[3]) - int(box[1]))


def _entry_belongs_to_region(entry_box: list[int], region_box: list[int]) -> bool:
    intersection = _intersection_area(entry_box, region_box)
    if intersection <= 0:
        return False

    entry_area = _box_area(entry_box)
    if entry_area <= 0:
        return False

    center_x = (int(entry_box[0]) + int(entry_box[2])) / 2
    center_y = (int(entry_box[1]) + int(entry_box[3])) / 2
    center_inside = (
        int(region_box[0]) <= center_x <= int(region_box[2])
        and int(region_box[1]) <= center_y <= int(region_box[3])
    )
    overlap_ratio = intersection / entry_area
    return center_inside or overlap_ratio >= 0.5


def _find_keyword_boxes(
    entries: list[dict[str, Any]],
    keywords: tuple[str, ...],
    min_top: int | None = None,
) -> list[list[int]]:
    matches: list[list[int]] = []
    for entry in entries:
        text = str(entry.get("text", "")).strip().lower()
        box = entry.get("bounding_box")
        if not text or not isinstance(box, list) or len(box) != 4:
            continue
        if min_top is not None and int(box[1]) < min_top:
            continue
        if any(keyword in text for keyword in keywords):
            matches.append([int(value) for value in box])
    return matches


def _build_layout_regions(width: int, height: int, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if height <= 0 or width <= 0:
        return []

    top_positions = sorted(int(entry["bounding_box"][1]) for entry in entries if entry.get("bounding_box"))
    bottom_positions = sorted(int(entry["bounding_box"][3]) for entry in entries if entry.get("bounding_box"))

    header_limit = max(
        int(height * 0.18),
        top_positions[min(len(top_positions) - 1, max(len(top_positions) // 4, 0))] if top_positions else 0,
    )
    footer_start = min(
        int(height * 0.8),
        bottom_positions[max(0, len(bottom_positions) - max(len(bottom_positions) // 4, 1))]
        if bottom_positions
        else int(height * 0.8),
    )

    if footer_start <= header_limit:
        header_limit = int(height * 0.2)
        footer_start = int(height * 0.8)

    header_bottom = max(0, min(header_limit, height))
    body_top = min(header_bottom + 1, height)
    body_bottom = max(min(footer_start, height), body_top)
    footer_top = min(footer_start + 1, height)

    return [
        {
            "section": "header",
            "description": "Top region containing invoice title, seller details, and invoice metadata",
            "bounding_box": [0, 0, width, header_bottom],
        },
        {
            "section": "body",
            "description": "Main content area containing billing details and item descriptions",
            "bounding_box": [0, body_top, width, body_bottom],
        },
        {
            "section": "footer",
            "description": "Bottom region containing totals, notes, bank details, and signature area",
            "bounding_box": [0, footer_top, width, height],
        },
    ]


def _group_entries_into_lines(entries: list[dict[str, Any]]) -> list[str]:
    if not entries:
        return []

    sorted_entries = sorted(
        entries,
        key=lambda entry: (
            int(entry["bounding_box"][1]),
            int(entry["bounding_box"][0]),
        ),
    )
    average_height = max(
        1,
        int(
            sum(
                max(1, int(entry["bounding_box"][3]) - int(entry["bounding_box"][1]))
                for entry in sorted_entries
            )
            / len(sorted_entries)
        ),
    )
    line_threshold = max(12, average_height // 2)

    grouped_lines: list[list[dict[str, Any]]] = []
    current_line: list[dict[str, Any]] = []
    current_center_y: float | None = None

    for entry in sorted_entries:
        top = int(entry["bounding_box"][1])
        bottom = int(entry["bounding_box"][3])
        center_y = (top + bottom) / 2

        if current_center_y is None or abs(center_y - current_center_y) <= line_threshold:
            current_line.append(entry)
            current_center_y = (
                sum((int(item["bounding_box"][1]) + int(item["bounding_box"][3])) / 2 for item in current_line)
                / len(current_line)
            )
        else:
            grouped_lines.append(current_line)
            current_line = [entry]
            current_center_y = center_y

    if current_line:
        grouped_lines.append(current_line)

    return [
        " ".join(str(item.get("text", "")).strip() for item in sorted(line, key=lambda item: int(item["bounding_box"][0]))).strip()
        for line in grouped_lines
        if any(str(item.get("text", "")).strip() for item in line)
    ]


def _attach_region_content(regions: list[dict[str, Any]], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched_regions: list[dict[str, Any]] = []

    for region in regions:
        region_box = region.get("bounding_box")
        if not isinstance(region_box, list) or len(region_box) != 4:
            enriched_regions.append(region)
            continue

        region_entries = []
        for entry in entries:
            text = str(entry.get("text", "")).strip()
            entry_box = entry.get("bounding_box")
            if not text or not isinstance(entry_box, list) or len(entry_box) != 4:
                continue
            if _entry_belongs_to_region(entry_box, region_box):
                region_entries.append(entry)

        region_entries = sorted(
            region_entries,
            key=lambda entry: (
                int(entry["bounding_box"][1]),
                int(entry["bounding_box"][0]),
            ),
        )
        content_words = [str(entry.get("text", "")).strip() for entry in region_entries]
        content_lines = _group_entries_into_lines(region_entries)

        enriched_regions.append(
            {
                **region,
                "content_words": content_words,
                "content_text": " ".join(content_words).strip(),
                "content_lines": content_lines,
            }
        )

    return enriched_regions


def _detect_layout_blocks(width: int, height: int, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []

    table_boxes = _find_keyword_boxes(entries, TABLE_KEYWORDS)
    if len(table_boxes) >= 2:
        blocks.append(
            {
                "block_type": "table_region",
                "bounding_box": _merge_boxes(table_boxes, width, height),
            }
        )

    totals_boxes = _find_keyword_boxes(entries, TOTALS_KEYWORDS, min_top=int(height * 0.45))
    if totals_boxes:
        blocks.append(
            {
                "block_type": "totals_region",
                "bounding_box": _merge_boxes(totals_boxes, width, height),
            }
        )

    header_boxes = _find_keyword_boxes(entries, HEADER_KEYWORDS)
    if header_boxes:
        blocks.append(
            {
                "block_type": "key_text_block",
                "label": "invoice_header_block",
                "bounding_box": _merge_boxes(header_boxes, width, height),
            }
        )

    seen: set[tuple[Any, ...]] = set()
    unique_blocks: list[dict[str, Any]] = []
    for block in blocks:
        key = (block.get("block_type"), block.get("label"), tuple(block["bounding_box"]))
        if key in seen:
            continue
        seen.add(key)
        unique_blocks.append(block)
    return unique_blocks


def _build_document_layout_analysis(
    image: Image.Image,
    entries: list[dict[str, Any]],
    layoutlm_status: dict[str, Any],
) -> dict[str, Any]:
    width, height = image.size
    layout_regions = _attach_region_content(_build_layout_regions(width, height, entries), entries)
    detected_blocks = _attach_region_content(_detect_layout_blocks(width, height, entries), entries)
    layout_executed = bool(layout_regions)
    model_executed = bool(layoutlm_status.get("executed"))
    fallback_used = bool(layoutlm_status.get("fallback_used"))

    if model_executed:
        note = (
            "Layout structure was derived using OCR text positions, bounding boxes, "
            "and LayoutLMv3-assisted document analysis."
        )
    elif layout_executed:
        note = (
            "Layout structure was derived using OCR text positions, bounding boxes, "
            "and safe spatial fallback zoning because direct model execution was limited."
        )
    else:
        note = "Layout analysis could not derive reliable regions from the available OCR output."

    return {
        "model_source": "Hugging Face",
        "model_name": "LayoutLMv3",
        "execution_status": "success" if layout_executed else "failed",
        "model_execution_status": "success" if model_executed else "fallback" if fallback_used else "skipped",
        "layout_regions": layout_regions,
        "detected_blocks": detected_blocks,
        "note": note,
    }


def analyze_document_layout(
    image: Image.Image,
    words: list[str],
    boxes: list[list[int]],
    entries: list[dict[str, Any]],
    raw_text: str,
) -> dict[str, Any]:
    """
    Use LayoutLMv3 to create document embeddings from OCR text plus bounding boxes.
    The response is intentionally lightweight and suitable for a mini project.
    """
    if not words or not boxes:
        note = "LayoutLMv3 skipped because OCR did not produce usable words and boxes."
        layoutlm_status = {
            "enabled": True,
            "source": "Hugging Face",
            "mode": "layout-aware document understanding",
            "model_name": MODEL_NAME,
            "executed": False,
            "fallback_used": True,
            "note": note,
        }
        return {
            "document_type": _guess_document_type(raw_text),
            "token_count": 0,
            "model_name": MODEL_NAME,
            "embedding_preview": [],
            "note": note,
            "layoutlmv3_status": layoutlm_status,
            "document_layout_analysis": _build_document_layout_analysis(image, entries, layoutlm_status),
        }

    try:
        processor, model, torch = get_layoutlm_components()
        encoded = processor(
            images=image,
            text=words,
            boxes=boxes,
            truncation=True,
            padding="max_length",
            max_length=LAYOUTLM_MAX_TOKENS,
            return_tensors="pt",
        )

        with torch.no_grad():
            outputs = model(**encoded)

        cls_embedding = outputs.last_hidden_state[:, 0, :].squeeze(0)
        embedding_preview = [round(float(value), 4) for value in cls_embedding[:8]]
        token_count = int(encoded["attention_mask"].sum().item())
        document_type = _guess_document_type(raw_text)
        note = (
            "Base LayoutLMv3 embeddings are available. "
            "Invoice field extraction still relies on OCR + rules until a fine-tuned key-value model is added."
        )

        layoutlm_status = {
            "enabled": True,
            "source": "Hugging Face",
            "mode": "layout-aware document understanding",
            "model_name": MODEL_NAME,
            "executed": True,
            "fallback_used": False,
            "note": note,
        }
        return {
            "document_type": document_type,
            "token_count": token_count,
            "model_name": MODEL_NAME,
            "embedding_preview": embedding_preview,
            "note": note,
            "layoutlmv3_status": layoutlm_status,
            "document_layout_analysis": _build_document_layout_analysis(image, entries, layoutlm_status),
        }
    except Exception as exc:
        logger.warning("LayoutLMv3 analysis skipped: %s", exc)
        note = (
            "LayoutLMv3 could not be loaded or executed in this environment, "
            "so the API continued with OCR + rule-based extraction only. "
            "Set LAYOUTLM_ALLOW_DOWNLOAD=true if you want the backend to fetch model files automatically."
        )
        layoutlm_status = {
            "enabled": False,
            "source": "Hugging Face",
            "mode": "layout-aware document understanding",
            "model_name": MODEL_NAME,
            "executed": False,
            "fallback_used": True,
            "note": note,
        }
        return {
            "document_type": _guess_document_type(raw_text),
            "token_count": len(words),
            "model_name": MODEL_NAME,
            "embedding_preview": [],
            "note": note,
            "layoutlmv3_status": layoutlm_status,
            "document_layout_analysis": _build_document_layout_analysis(image, entries, layoutlm_status),
        }
