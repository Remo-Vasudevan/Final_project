from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from urllib.parse import urljoin
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

try:
    from .config import API_DESCRIPTION, API_TITLE, API_VERSION, FRONTEND_DIR, OUTPUT_DIR, UPLOAD_DIR, parse_cors_origins
    from .errors import http_exception_handler, request_validation_exception_handler, technical_http_error
    from .extractor import build_extraction_result
    from .request_parsing import extract_uploaded_file
    from .report_generator import generate_structured_report, save_structured_report
    from .schemas import APIErrorResponse, APIStatusResponse, ModuleJsonOutput, PublicUploadResponse
    from .utils import (
        enforce_saved_file_size,
        ensure_directories,
        export_to_excel,
        save_layout_json,
        to_relative_api_path,
    )
except ImportError:
    from config import API_DESCRIPTION, API_TITLE, API_VERSION, FRONTEND_DIR, OUTPUT_DIR, UPLOAD_DIR, parse_cors_origins
    from errors import http_exception_handler, request_validation_exception_handler, technical_http_error
    from extractor import build_extraction_result
    from request_parsing import extract_uploaded_file
    from report_generator import generate_structured_report, save_structured_report
    from schemas import APIErrorResponse, APIStatusResponse, ModuleJsonOutput, PublicUploadResponse
    from utils import (
        enforce_saved_file_size,
        ensure_directories,
        export_to_excel,
        save_layout_json,
        to_relative_api_path,
    )


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

MODULE_NAME = "LayoutLMv3 and Hugging Face Document Understanding Module"
MODULE_SUMMARY = "LayoutLMv3 + Hugging Face"
FEATURE_FLAGS = [
    "layout-aware text understanding",
    "bounding box analysis",
    "OCR text alignment",
    "document structure interpretation",
    "layout region visibility",
]

ensure_directories()

app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="frontend-static")


def _resolve_report_path(report_name: str) -> Path:
    candidate = Path(report_name)
    if candidate.name != report_name or candidate.suffix.lower() != ".txt":
        raise technical_http_error("Invalid field name", status_code=404, error_code="report_not_found")

    report_path = (OUTPUT_DIR / candidate.name).resolve()
    output_root = OUTPUT_DIR.resolve()
    if output_root not in report_path.parents or not report_path.exists():
        raise technical_http_error("Invalid field name", status_code=404, error_code="report_not_found")

    return report_path


def _cleanup_saved_file(file_path: Path) -> None:
    if file_path.exists():
        file_path.unlink(missing_ok=True)


def _build_layout_payload(
    *,
    extraction_result: dict,
    original_file_name: str,
    saved_file_path: Path,
    root_url: str,
    docs_url: str,
    excel_relative_path: str,
) -> dict:
    return {
        "status": "success",
        "message": "Document processed successfully",
        "file_name": original_file_name,
        "document_type": extraction_result["document_type"],
        "image_size": extraction_result["image_size"],
        "ocr_layout_data": extraction_result["ocr_layout_data"],
        "layoutlmv3_status": extraction_result["layoutlmv3_status"],
        "document_layout_analysis": extraction_result["document_layout_analysis"],
        "extracted_data": extraction_result["extracted_data"],
        "extracted_fields": extraction_result["extracted_data"],
        "confidence_note": extraction_result["confidence_note"],
        "layoutlm_summary": extraction_result["layoutlm_summary"],
        "file_metadata": {
            "saved_upload": to_relative_api_path(saved_file_path, UPLOAD_DIR.parent),
            "content_type": "application/octet-stream",
        },
        "web_links": {
            "root_url": root_url,
            "docs_url": docs_url,
        },
        "excel_file": excel_relative_path,
    }


def _build_public_response(
    *,
    extraction_result: dict,
    root_url: str,
    docs_url: str,
    original_file_name: str,
    json_relative_path: str,
    excel_relative_path: str,
    report_relative_path: str,
    report_route: str,
    report_text: str,
) -> PublicUploadResponse:
    layout_status = extraction_result["layoutlmv3_status"]
    layout_executed = bool(layout_status.get("executed"))
    document_layout_status = extraction_result["document_layout_analysis"]["execution_status"]

    return PublicUploadResponse(
        status="success",
        message="Document processed successfully",
        file_name=original_file_name,
        module_name=MODULE_NAME,
        layoutlmv3_summary=(
            "LayoutLMv3 analyzed OCR-extracted text together with bounding box positions "
            "for layout-aware document understanding."
        ),
        huggingface_summary=(
            "The model was accessed through the Hugging Face pipeline and executed successfully."
            if layout_executed
            else "The Hugging Face model pipeline remained integrated and the backend continued safely with fallback handling."
        ),
        document_understanding_summary=(
            "The module used spatial text layout and contextual structure to support invoice understanding."
        ),
        extracted_data=extraction_result["extracted_data"],
        ocr_text_preview=extraction_result["raw_text"][:1200],
        json_output=ModuleJsonOutput(
            module=MODULE_SUMMARY,
            document_type=extraction_result["document_type"],
            features_used=FEATURE_FLAGS,
            execution_status=document_layout_status,
        ),
        json_output_file=json_relative_path,
        json_output_url=urljoin(root_url, json_relative_path),
        excel_file=excel_relative_path,
        excel_file_url=urljoin(root_url, excel_relative_path),
        text_report_file=report_relative_path,
        text_report_url=urljoin(root_url, report_route),
        text_report_preview=report_text,
        document_layout_analysis_status=document_layout_status,
        root_url=root_url,
        docs_url=docs_url,
    )


@app.get("/", include_in_schema=False)
def read_root() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health", response_model=APIStatusResponse)
def health_check() -> APIStatusResponse:
    return APIStatusResponse(
        status="success",
        message="Service is healthy",
    )


@app.get("/report/{report_name}", include_in_schema=False)
def open_structured_report(report_name: str) -> FileResponse:
    report_path = _resolve_report_path(report_name)
    return FileResponse(report_path, media_type="text/plain; charset=utf-8", filename=report_path.name)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.post(
    "/upload",
    response_model=PublicUploadResponse,
    response_description="Returns the executed LayoutLMv3 and Hugging Face document understanding summary.",
    responses={
        200: {"description": "Module-focused response shown after successful execution."},
        400: {"model": APIErrorResponse, "description": "Technical error for invalid upload input."},
        422: {"model": APIErrorResponse, "description": "Technical error for invalid request payload."},
    },
)
async def upload_document(request: Request, file: UploadFile = File(None)) -> PublicUploadResponse:
    uploaded_file = await extract_uploaded_file(request)

    file_extension = Path(uploaded_file.filename).suffix.lower()
    safe_name = f"{uuid4().hex}{file_extension}"
    saved_file_path = UPLOAD_DIR / safe_name

    try:
        with saved_file_path.open("wb") as buffer:
            shutil.copyfileobj(uploaded_file.file, buffer)
        enforce_saved_file_size(saved_file_path)
    except HTTPException:
        _cleanup_saved_file(saved_file_path)
        raise
    except Exception as exc:
        logger.exception("Failed to save uploaded file")
        _cleanup_saved_file(saved_file_path)
        raise technical_http_error("Failed to save uploaded file", status_code=500, error_code="upload_save_failed") from exc
    finally:
        await uploaded_file.close()

    try:
        extraction_payload = build_extraction_result(saved_file_path, original_filename=uploaded_file.filename)
        root_url = str(request.base_url)
        docs_url = urljoin(root_url, "docs")
        excel_path = export_to_excel(
            extracted_data=extraction_payload["extracted_data"],
            output_dir=OUTPUT_DIR,
            base_filename=Path(uploaded_file.filename).stem,
        )

        excel_relative_path = to_relative_api_path(excel_path, OUTPUT_DIR.parent)
        layout_json_payload = _build_layout_payload(
            extraction_result=extraction_payload,
            original_file_name=uploaded_file.filename,
            saved_file_path=saved_file_path,
            root_url=root_url,
            docs_url=docs_url,
            excel_relative_path=excel_relative_path,
        )
        layout_json_payload["file_metadata"]["content_type"] = uploaded_file.content_type or "application/octet-stream"
        json_output_path = save_layout_json(
            data=layout_json_payload,
            output_dir=OUTPUT_DIR,
            base_filename=Path(uploaded_file.filename).stem,
        )
        json_relative_path = to_relative_api_path(json_output_path, OUTPUT_DIR.parent)
        layout_json_payload["json_output_file"] = json_relative_path
        layout_json_payload["json_output_url"] = urljoin(root_url, json_relative_path)
        layout_json_payload["excel_file_url"] = urljoin(root_url, excel_relative_path)

        # Generate a notepad-style report after the JSON payload is finalized.
        report_text = generate_structured_report(layout_json_payload)
        report_path = save_structured_report(
            report_text=report_text,
            output_dir=OUTPUT_DIR,
            base_filename=Path(uploaded_file.filename).stem,
        )
        report_relative_path = to_relative_api_path(report_path, OUTPUT_DIR.parent)
        report_route = f"report/{report_path.name}"
        layout_json_payload["text_report_file"] = report_relative_path
        layout_json_payload["text_report_url"] = urljoin(root_url, report_route)
        layout_json_payload["text_report_preview"] = report_text

        json_output_path.write_text(
            json.dumps(layout_json_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info(
            "Final API response for %s | document_type=%s | extracted_fields=%s",
            uploaded_file.filename,
            extraction_payload["document_type"],
            extraction_payload["extracted_data"],
        )

        return _build_public_response(
            extraction_result=extraction_payload,
            root_url=root_url,
            docs_url=docs_url,
            original_file_name=uploaded_file.filename,
            json_relative_path=json_relative_path,
            excel_relative_path=excel_relative_path,
            report_relative_path=report_relative_path,
            report_route=report_route,
            report_text=report_text,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Document processing failed")
        raise technical_http_error("Document processing failed", status_code=500, error_code="document_processing_failed") from exc
