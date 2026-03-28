from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
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

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
MAX_UPLOAD_SIZE_MB = 10
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

IMAGE_SIZE = (1000, 1000)
LAYOUTLM_MAX_TOKENS = 512

SUPPORTED_DOCUMENT_TYPES = ["invoice", "receipt", "document", "unknown"]
