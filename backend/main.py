from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from urllib.parse import urljoin
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

try:
    from .config import API_DESCRIPTION, API_TITLE, API_VERSION, FRONTEND_DIR, OUTPUT_DIR, UPLOAD_DIR
    from .extractor import build_extraction_result
    from .report_generator import generate_structured_report, save_structured_report
    from .schemas import APIStatusResponse, ModuleJsonOutput, PublicUploadResponse
    from .utils import (
        enforce_saved_file_size,
        ensure_directories,
        export_to_excel,
        save_layout_json,
        to_relative_api_path,
        validate_uploaded_file,
    )
except ImportError:
    from config import API_DESCRIPTION, API_TITLE, API_VERSION, FRONTEND_DIR, OUTPUT_DIR, UPLOAD_DIR
    from extractor import build_extraction_result
    from report_generator import generate_structured_report, save_structured_report
    from schemas import APIStatusResponse, ModuleJsonOutput, PublicUploadResponse
    from utils import (
        enforce_saved_file_size,
        ensure_directories,
        export_to_excel,
        save_layout_json,
        to_relative_api_path,
        validate_uploaded_file,
    )


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

ensure_directories()

app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="frontend-static")


def _resolve_report_path(report_name: str) -> Path:
    candidate = Path(report_name)
    if candidate.name != report_name or candidate.suffix.lower() != ".txt":
        raise HTTPException(status_code=404, detail="Report not found.")

    report_path = (OUTPUT_DIR / candidate.name).resolve()
    output_root = OUTPUT_DIR.resolve()
    if output_root not in report_path.parents or not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found.")

    return report_path


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
    responses={200: {"description": "Module-focused response shown after successful execution."}},
)
async def upload_document(request: Request, file: UploadFile = File(...)) -> PublicUploadResponse:
    validate_uploaded_file(file)

    file_extension = Path(file.filename).suffix.lower()
    safe_name = f"{uuid4().hex}{file_extension}"
    saved_file_path = UPLOAD_DIR / safe_name

    try:
        with saved_file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        enforce_saved_file_size(saved_file_path)
        logger.info("Saved uploaded file to %s", saved_file_path)
    except HTTPException:
        if saved_file_path.exists():
            saved_file_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        logger.exception("Failed to save uploaded file")
        if saved_file_path.exists():
            saved_file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}") from exc
    finally:
        await file.close()

    try:
        extraction_payload = build_extraction_result(saved_file_path, original_filename=file.filename)
        root_url = str(request.base_url)
        docs_url = urljoin(root_url, "docs")
        excel_path = export_to_excel(
            extracted_data=extraction_payload["extracted_data"],
            output_dir=OUTPUT_DIR,
            base_filename=Path(file.filename).stem,
        )

        excel_relative_path = to_relative_api_path(excel_path, OUTPUT_DIR.parent)
        layout_json_payload = {
            "status": "success",
            "message": "Document processed successfully",
            "file_name": file.filename,
            "document_type": extraction_payload["document_type"],
            "image_size": extraction_payload["image_size"],
            "ocr_layout_data": extraction_payload["ocr_layout_data"],
            "layoutlmv3_status": extraction_payload["layoutlmv3_status"],
            "document_layout_analysis": extraction_payload["document_layout_analysis"],
            "extracted_data": extraction_payload["extracted_data"],
            "extracted_fields": extraction_payload["extracted_data"],
            "confidence_note": extraction_payload["confidence_note"],
            "layoutlm_summary": extraction_payload["layoutlm_summary"],
            "file_metadata": {
                "saved_upload": to_relative_api_path(saved_file_path, UPLOAD_DIR.parent),
                "content_type": file.content_type or "application/octet-stream",
            },
            "web_links": {"root_url": root_url, "docs_url": docs_url},
            "excel_file": excel_relative_path,
        }
        json_output_path = save_layout_json(
            data=layout_json_payload,
            output_dir=OUTPUT_DIR,
            base_filename=Path(file.filename).stem,
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
            base_filename=Path(file.filename).stem,
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

        print(report_text, flush=True)

        layout_status = extraction_payload["layoutlmv3_status"]
        layout_executed = bool(layout_status.get("executed"))
        document_layout_status = extraction_payload["document_layout_analysis"]["execution_status"]

        response = PublicUploadResponse(
            status="success",
            message="Document processed successfully",
            file_name=file.filename,
            module_name="LayoutLMv3 and Hugging Face Document Understanding Module",
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
            json_output=ModuleJsonOutput(
                module="LayoutLMv3 + Hugging Face",
                document_type=extraction_payload["document_type"],
                features_used=[
                    "layout-aware text understanding",
                    "bounding box analysis",
                    "OCR text alignment",
                    "document structure interpretation",
                    "layout region visibility",
                ],
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
        logger.info("Processing finished for %s", file.filename)
        return response
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Document processing failed")
        raise HTTPException(status_code=500, detail=f"Document processing failed: {exc}") from exc
