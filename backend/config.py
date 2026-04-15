import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
SAMPLE_DATA_DIR = BASE_DIR / "sample_data"

API_TITLE = "Smart Invoice / Document Extractor API"
API_DESCRIPTION = (
    "Upload invoice or document images, extract OCR text and structured fields, "
    "and export results to Excel."
)
API_VERSION = "1.0.0"

MODEL_NAME = "microsoft/layoutlmv3-base"
OCR_LANGUAGES = ["en"]
LAYOUTLM_ALLOW_DOWNLOAD = os.getenv("LAYOUTLM_ALLOW_DOWNLOAD", "").strip().lower() in {"1", "true", "yes", "on"}
UPLOAD_FIELD_ALIASES = ("file", "document", "upload", "image")
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/bmp",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/tif",
    "image/tiff",
    "application/octet-stream",
}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
MAX_UPLOAD_SIZE_MB = 10
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

IMAGE_SIZE = (1000, 1000)
LAYOUTLM_MAX_TOKENS = 512

SUPPORTED_DOCUMENT_TYPES = ["invoice", "receipt", "document", "unknown"]


def parse_cors_origins() -> list[str]:
    raw_origins = os.getenv(
        "BACKEND_CORS_ORIGINS",
        ",".join(
            [
                "http://127.0.0.1:4173",
                "http://localhost:4173",
                "http://127.0.0.1:5173",
                "http://localhost:5173",
                "http://127.0.0.1:3000",
                "http://localhost:3000",
                "http://127.0.0.1:8001",
                "http://localhost:8001",
            ]
        ),
    )
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
