import logging
from typing import Any

import easyocr
import numpy as np

from config import OCR_LANGUAGES
from utils import normalize_box, polygon_to_box, preprocess_image_for_ocr


logger = logging.getLogger(__name__)
_ocr_reader = None


def get_ocr_reader() -> easyocr.Reader:
    global _ocr_reader
    if _ocr_reader is None:
        logger.info("Loading EasyOCR reader")
        _ocr_reader = easyocr.Reader(OCR_LANGUAGES, gpu=False)
    return _ocr_reader


def _extract_with_tesseract(image_array: np.ndarray, width: int, height: int) -> dict[str, Any]:
    logger.warning("Falling back to pytesseract OCR")
    tesseract_data = pytesseract.image_to_data(
        image_array,
        output_type=pytesseract.Output.DICT,
    )

    words: list[str] = []
    boxes: list[list[int]] = []
    bounding_boxes: list[list[int]] = []
    lines: list[str] = []
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
        lines.append(clean_text)
        confidences.append(confidence)
        entries.append(
            {
                "text": clean_text,
                "bounding_box": bounding_box,
                "normalized_box": normalized_box,
                "confidence": round(confidence, 4),
            }
        )

    return {
        "words": words,
        "boxes": boxes,
        "bounding_boxes": bounding_boxes,
        "normalized_boxes": boxes,
        "entries": entries,
        "confidences": confidences,
        "raw_text": "\n".join(lines),
    }


def extract_ocr_data(image_path: str) -> dict[str, Any]:
    """
    Run OCR and return words, bounding boxes, normalized boxes, confidence values,
    and raw text while preserving the existing OCR flow.
    """
    processed_image = preprocess_image_for_ocr(image_path)
    width, height = processed_image.size
    image_array = np.array(processed_image)

    try:
        reader = get_ocr_reader()
        results = reader.readtext(image_array, detail=1, paragraph=False)

        words: list[str] = []
        boxes: list[list[int]] = []
        bounding_boxes: list[list[int]] = []
        lines: list[str] = []
        confidences: list[float] = []
        entries: list[dict[str, Any]] = []

        for raw_box, text, confidence in results:
            clean_text = str(text).strip()
            if not clean_text:
                continue

            bounding_box = polygon_to_box(raw_box)
            normalized_box = normalize_box(raw_box, width, height)
            words.append(clean_text)
            boxes.append(normalized_box)
            bounding_boxes.append(bounding_box)
            lines.append(clean_text)
            confidences.append(float(confidence))
            entries.append(
                {
                    "text": clean_text,
                    "bounding_box": bounding_box,
                    "normalized_box": normalized_box,
                    "confidence": round(float(confidence), 4),
                }
            )

        payload = {
            "words": words,
            "boxes": boxes,
            "bounding_boxes": bounding_boxes,
            "normalized_boxes": boxes,
            "entries": entries,
            "confidences": confidences,
            "raw_text": "\n".join(lines),
        }
    except Exception as exc:
        logger.warning("EasyOCR failed, attempting pytesseract fallback: %s", exc)
        payload = _extract_with_tesseract(image_array, width, height)

    logger.info("OCR extracted %s text items", len(payload["words"]))
    return {
        **payload,
        "image_size": {"width": width, "height": height},
        "image": processed_image,
    }






