from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from fastapi import HTTPException, UploadFile
from openpyxl import Workbook
from PIL import Image, ImageFilter, ImageOps

try:
    from .config import (
        ALLOWED_EXTENSIONS,
        ALLOWED_IMAGE_CONTENT_TYPES,
        MAX_UPLOAD_SIZE_BYTES,
        OUTPUT_DIR,
        SAMPLE_DATA_DIR,
        UPLOAD_DIR,
    )
    from .errors import technical_http_error
except ImportError:
    from config import (
        ALLOWED_EXTENSIONS,
        ALLOWED_IMAGE_CONTENT_TYPES,
        MAX_UPLOAD_SIZE_BYTES,
        OUTPUT_DIR,
        SAMPLE_DATA_DIR,
        UPLOAD_DIR,
    )
    from errors import technical_http_error


SAFE_IDENTIFIER_PATTERN = re.compile(r"[^a-z0-9]+")
FILENAME_FALLBACK = "document"


def ensure_directories() -> None:
    for directory in (UPLOAD_DIR, OUTPUT_DIR, SAMPLE_DATA_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def normalize_identifier(value: Any) -> str:
    normalized = SAFE_IDENTIFIER_PATTERN.sub("_", str(value).strip().lower()).strip("_")
    return normalized


def validate_uploaded_file(file: UploadFile) -> None:
    if not file.filename:
        raise technical_http_error("Invalid field name", error_code="invalid_field_name")

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise technical_http_error(
            f"Unsupported input keyword. Allowed file types: {allowed}",
            error_code="unsupported_input",
        )

    file_size = getattr(file, "size", None)
    if file_size and int(file_size) > MAX_UPLOAD_SIZE_BYTES:
        raise technical_http_error(
            f"File exceeds the {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB upload limit",
            error_code="file_too_large",
        )

    content_type = (file.content_type or "").strip().lower()
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise technical_http_error("Unsupported input keyword", error_code="unsupported_input")


def enforce_saved_file_size(file_path: Path) -> None:
    if file_path.stat().st_size > MAX_UPLOAD_SIZE_BYTES:
        raise technical_http_error(
            f"File exceeds the {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB upload limit",
            error_code="file_too_large",
        )


def preprocess_image_for_ocr(image_path: str) -> Image.Image:
    with Image.open(image_path) as source_image:
        base_image = ImageOps.exif_transpose(source_image).convert("RGB")
        return base_image


def build_ocr_fallback_variants(image_path: str) -> list[tuple[str, Image.Image]]:
    with Image.open(image_path) as source_image:
        base_image = ImageOps.exif_transpose(source_image).convert("RGB")
        grayscale = ImageOps.autocontrast(ImageOps.grayscale(base_image)).convert("RGB")
        upscaled = base_image.resize((base_image.width * 2, base_image.height * 2))
        sharpened = ImageOps.autocontrast(base_image.filter(ImageFilter.SHARPEN))

        return [
            ("grayscale", grayscale),
            ("upscaled", upscaled),
            ("sharpened", sharpened),
        ]


def polygon_to_box(box: Iterable[Iterable[float]]) -> list[int]:
    x_coordinates = [point[0] for point in box]
    y_coordinates = [point[1] for point in box]
    return [
        int(min(x_coordinates)),
        int(min(y_coordinates)),
        int(max(x_coordinates)),
        int(max(y_coordinates)),
    ]


def normalize_box(box: Iterable[Iterable[float]], width: int, height: int) -> list[int]:
    if width <= 0 or height <= 0:
        return [0, 0, 0, 0]

    x_coordinates = [point[0] for point in box]
    y_coordinates = [point[1] for point in box]

    left = max(0, min(int(min(x_coordinates) / width * 1000), 1000))
    top = max(0, min(int(min(y_coordinates) / height * 1000), 1000))
    right = max(0, min(int(max(x_coordinates) / width * 1000), 1000))
    bottom = max(0, min(int(max(y_coordinates) / height * 1000), 1000))
    return [left, top, right, bottom]


def export_to_excel(extracted_data: dict, output_dir: Path, base_filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = safe_filename(base_filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = output_dir / f"{safe_name}_{timestamp}.xlsx"

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Extraction"

    headers = list(extracted_data.keys())
    values = []
    for header in headers:
        raw_value = extracted_data.get(header, "")
        if isinstance(raw_value, list):
            values.append(json.dumps(raw_value, ensure_ascii=False))
        elif isinstance(raw_value, dict):
            values.append(json.dumps(raw_value, ensure_ascii=False))
        else:
            values.append(raw_value)
    worksheet.append(headers)
    worksheet.append(values)
    workbook.save(file_path)
    return file_path


def save_layout_json(data: dict, output_dir: Path, base_filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = safe_filename(base_filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = output_dir / f"{safe_name}_layout_data_{timestamp}.json"
    file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return file_path


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"_+", "_", "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip()))
    return cleaned.strip("_") or FILENAME_FALLBACK


def to_relative_api_path(path: Path, root_dir: Path) -> str:
    return path.relative_to(root_dir).as_posix()
