from __future__ import annotations

import logging
from importlib import import_module
from typing import Any

import numpy as np

try:
    from .config import OCR_LANGUAGES
    from .utils import build_ocr_fallback_variants, normalize_box, polygon_to_box, preprocess_image_for_ocr
except ImportError:
    from config import OCR_LANGUAGES
    from utils import build_ocr_fallback_variants, normalize_box, polygon_to_box, preprocess_image_for_ocr


logger = logging.getLogger(__name__)
_ocr_reader = None


def _load_optional_module(module_name: str) -> Any | None:
    try:
        return import_module(module_name)
    except ImportError:
        return None


def get_ocr_reader() -> Any:
    global _ocr_reader
    if _ocr_reader is None:
        easyocr_module = _load_optional_module("easyocr")
        if easyocr_module is None:
            raise RuntimeError("EasyOCR is not installed.")
        _ocr_reader = easyocr_module.Reader(OCR_LANGUAGES, gpu=False)
    return _ocr_reader


def _empty_ocr_payload(note: str) -> dict[str, Any]:
    return {
        "full_text": "",
        "words": [],
        "boxes": [],
        "bounding_boxes": [],
        "normalized_boxes": [],
        "entries": [],
        "confidences": [],
        "raw_text": "",
        "note": note,
    }


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
    line_threshold = max(10, average_height // 2)
    lines: list[list[dict[str, Any]]] = []
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
            lines.append(current_line)
            current_line = [entry]
            current_center_y = center_y

    if current_line:
        lines.append(current_line)

    return [
        " ".join(
            str(item.get("text", "")).strip()
            for item in sorted(line, key=lambda item: int(item["bounding_box"][0]))
            if str(item.get("text", "")).strip()
        ).strip()
        for line in lines
    ]


def _score_ocr_payload(payload: dict[str, Any]) -> float:
    words = payload.get("words", [])
    confidences = payload.get("confidences", [])
    lines = payload.get("lines", [])
    text = payload.get("raw_text", "")
    confidence_score = sum(confidences) * 15 if confidences else 0
    character_score = sum(char.isalnum() for char in text)
    structure_bonus = len(lines) * 10 + len(words) * 4
    return confidence_score + character_score + structure_bonus


def _build_easyocr_payload(results: list[Any], width: int, height: int, variant_name: str) -> dict[str, Any]:
    words: list[str] = []
    boxes: list[list[int]] = []
    bounding_boxes: list[list[int]] = []
    confidences: list[float] = []
    entries: list[dict[str, Any]] = []

    for raw_box, text, confidence in results:
        clean_text = str(text).strip()
        if not clean_text:
            continue

        bounding_box = polygon_to_box(raw_box)
        normalized_box = normalize_box(raw_box, width, height)
        numeric_confidence = float(confidence)

        words.append(clean_text)
        boxes.append(normalized_box)
        bounding_boxes.append(bounding_box)
        confidences.append(numeric_confidence)
        entries.append(
            {
                "text": clean_text,
                "bounding_box": bounding_box,
                "normalized_box": normalized_box,
                "confidence": round(numeric_confidence, 4),
            }
        )

    lines = [line for line in _group_entries_into_lines(entries) if line]
    raw_text = "\n".join(lines)
    return {
        "full_text": raw_text,
        "words": words,
        "boxes": boxes,
        "bounding_boxes": bounding_boxes,
        "normalized_boxes": boxes,
        "entries": entries,
        "lines": lines,
        "confidences": confidences,
        "raw_text": raw_text,
        "note": "" if variant_name == "default" else f"OCR used the {variant_name} image fallback.",
        "ocr_variant": variant_name,
    }


def _extract_with_tesseract(image_array: np.ndarray, width: int, height: int) -> dict[str, Any]:
    pytesseract_module = _load_optional_module("pytesseract")
    if pytesseract_module is None:
        raise RuntimeError("pytesseract is not installed.")

    logger.warning("Falling back to pytesseract OCR")
    tesseract_data = pytesseract_module.image_to_data(
        image_array,
        output_type=pytesseract_module.Output.DICT,
    )

    words: list[str] = []
    boxes: list[list[int]] = []
    bounding_boxes: list[list[int]] = []
    confidences: list[float] = []
    entries: list[dict[str, Any]] = []

    total_items = len(tesseract_data.get("text", []))
    for index in range(total_items):
        clean_text = str(tesseract_data["text"][index]).strip()
        if not clean_text:
            continue

        left = int(tesseract_data["left"][index])
        top = int(tesseract_data["top"][index])
        box_width = int(tesseract_data["width"][index])
        box_height = int(tesseract_data["height"][index])
        confidence_raw = str(tesseract_data["conf"][index]).strip()

        bounding_box = [left, top, left + box_width, top + box_height]
        polygon = [
            [left, top],
            [left + box_width, top],
            [left + box_width, top + box_height],
            [left, top + box_height],
        ]
        normalized_box = normalize_box(polygon, width, height)

        try:
            confidence = max(float(confidence_raw), 0.0) / 100
        except ValueError:
            confidence = 0.0

        words.append(clean_text)
        boxes.append(normalized_box)
        bounding_boxes.append(bounding_box)
        confidences.append(confidence)
        entries.append(
            {
                "text": clean_text,
                "bounding_box": bounding_box,
                "normalized_box": normalized_box,
                "confidence": round(confidence, 4),
            }
        )

    lines = [line for line in _group_entries_into_lines(entries) if line]
    raw_text = "\n".join(lines)
    return {
        "full_text": raw_text,
        "words": words,
        "boxes": boxes,
        "bounding_boxes": bounding_boxes,
        "normalized_boxes": boxes,
        "entries": entries,
        "lines": lines,
        "confidences": confidences,
        "raw_text": raw_text,
        "note": "EasyOCR was unavailable, so pytesseract fallback OCR was used.",
        "ocr_variant": "tesseract",
    }


def _extract_with_easyocr(image_path: str) -> dict[str, Any]:
    reader = get_ocr_reader()
    primary_image = preprocess_image_for_ocr(image_path)
    width, height = primary_image.size

    primary_results = reader.readtext(np.array(primary_image), detail=1, paragraph=False)
    best_payload = _build_easyocr_payload(primary_results, width, height, "default")
    best_score = _score_ocr_payload(best_payload)
    selected_image = primary_image

    if len(best_payload["words"]) < 6 or sum(char.isalnum() for char in best_payload["raw_text"]) < 30:
        for variant_name, variant_image in build_ocr_fallback_variants(image_path):
            variant_width, variant_height = variant_image.size
            variant_results = reader.readtext(np.array(variant_image), detail=1, paragraph=False)
            variant_payload = _build_easyocr_payload(variant_results, variant_width, variant_height, variant_name)
            variant_score = _score_ocr_payload(variant_payload)
            if variant_score > best_score:
                best_payload = variant_payload
                best_score = variant_score
                selected_image = variant_image

    logger.info(
        "OCR variant selected: %s | words=%s | lines=%s | score=%.2f",
        best_payload["ocr_variant"],
        len(best_payload["words"]),
        len(best_payload["lines"]),
        best_score,
    )
    logger.info("OCR parsed tokens preview: %s", best_payload["words"][:20])
    logger.info("OCR bounding boxes detected: %s", len(best_payload["bounding_boxes"]))
    logger.info("OCR raw text preview: %s", best_payload["raw_text"][:500] or "<empty>")
    selected_width, selected_height = selected_image.size
    return {
        **best_payload,
        "image_size": {"width": selected_width, "height": selected_height},
        "image": selected_image,
    }


def extract_ocr_data(image_path: str) -> dict[str, Any]:
    """
    Run OCR and return words, bounding boxes, normalized boxes, confidence values,
    and raw text while preserving the existing OCR flow.
    """
    try:
        return _extract_with_easyocr(image_path)
    except Exception as easyocr_exc:
        logger.warning("EasyOCR failed, attempting pytesseract fallback: %s", easyocr_exc)
        try:
            processed_image = preprocess_image_for_ocr(image_path)
            width, height = processed_image.size
            image_array = np.array(processed_image)
            payload = _extract_with_tesseract(image_array, width, height)
        except Exception as tesseract_exc:
            note = (
                "OCR engines were unavailable or could not read the file. "
                f"EasyOCR failed: {easyocr_exc}. pytesseract failed: {tesseract_exc}."
            )
            logger.exception("All OCR engines failed")
            payload = _empty_ocr_payload(note)

    return {
        **payload,
        "image_size": payload.get("image_size", {"width": width, "height": height}),
        "image": processed_image,
    }
