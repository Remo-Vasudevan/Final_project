import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2
import pandas as pd
from fastapi import HTTPException, UploadFile
from PIL import Image

from config import ALLOWED_EXTENSIONS, OUTPUT_DIR, SAMPLE_DATA_DIR, UPLOAD_DIR


def ensure_directories() -> None:
    for directory in (UPLOAD_DIR, OUTPUT_DIR, SAMPLE_DATA_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def validate_uploaded_file(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed file types: {allowed}",
        )


def preprocess_image_for_ocr(image_path: str) -> Image.Image:
    """
    Apply a light preprocessing pipeline that improves OCR readability
    without making the mini project difficult to understand.
    """
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Unable to read image from path: {image_path}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    denoised = cv2.GaussianBlur(gray, (3, 3), 0)
    thresholded = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    rgb_image = cv2.cvtColor(thresholded, cv2.COLOR_GRAY2RGB)
    return Image.fromarray(rgb_image)


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
    x_coordinates = [point[0] for point in box]
    y_coordinates = [point[1] for point in box]

    left = max(0, min(int(min(x_coordinates) / width * 1000), 1000))
    top = max(0, min(int(min(y_coordinates) / height * 1000), 1000))
    right = max(0, min(int(max(x_coordinates) / width * 1000), 1000))
    bottom = max(0, min(int(max(y_coordinates) / height * 1000), 1000))
    return [left, top, right, bottom]


def export_to_excel(extracted_data: dict, output_dir: Path, base_filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    dataframe = pd.DataFrame([extracted_data])
    safe_name = safe_filename(base_filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = output_dir / f"{safe_name}_{timestamp}.xlsx"
    dataframe.to_excel(file_path, index=False, engine="openpyxl")
    return file_path


def save_layout_json(data: dict, output_dir: Path, base_filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = safe_filename(base_filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = output_dir / f"{safe_name}_layout_data_{timestamp}.json"
    file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return file_path


def safe_filename(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())
    return cleaned or "document"


def to_relative_api_path(path: Path, root_dir: Path) -> str:
    return path.relative_to(root_dir).as_posix()
