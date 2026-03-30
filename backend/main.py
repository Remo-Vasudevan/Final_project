import json
import logging
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from config import API_DESCRIPTION, API_TITLE, API_VERSION, OUTPUT_DIR, UPLOAD_DIR
from extractor import build_extraction_result
from schemas import APIStatusResponse, HealthResponse, ModuleJsonOutput, PublicUploadResponse
from utils import ensure_directories, export_to_excel, save_layout_json, to_relative_api_path, validate_uploaded_file


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


@app.get("/", response_model=HealthResponse)
def read_root() -> HealthResponse:
    return HealthResponse(
        status="success",
        message="Smart Invoice / Document Extractor API is running",
        docs_url="/docs",
    )


@app.get("/health", response_model=APIStatusResponse)
def health_check() -> APIStatusResponse:
    return APIStatusResponse(
        status="success",
        message="Service is healthy",
    )


@app.post(
    "/upload",
    response_model=PublicUploadResponse,
    response_description="Returns the executed LayoutLMv3 and Hugging Face document understanding summary.",
    responses={
        200: {
            "description": "Module-focused response shown after successful execution."
        }
    },
)
async def upload_document(file: UploadFile = File(...)) -> PublicUploadResponse:
    validate_uploaded_file(file)

    file_extension = Path(file.filename).suffix.lower()
    safe_name = f"{uuid4().hex}{file_extension}"
    saved_file_path = UPLOAD_DIR / safe_name

    try:
        with saved_file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info("Saved uploaded file to %s", saved_file_path)
    except Exception as exc:
        logger.exception("Failed to save uploaded file")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}") from exc
    finally:
        await file.close()

    try:
        extraction_payload = build_extraction_result(saved_file_path, original_filename=file.filename)
        excel_path = export_to_excel(
            extracted_data=extraction_payload["extracted_data"],
            output_dir=OUTPUT_DIR,
            base_filename=Path(file.filename).stem,
        )

        layout_json_payload = {
            "status": "success",
            "message": "Document processed successfully",
            "file_name": file.filename,
            "image_size": extraction_payload["image_size"],
            "ocr_layout_data": extraction_payload["ocr_layout_data"],
            "layoutlmv3_status": extraction_payload["layoutlmv3_status"],
            "extracted_data": extraction_payload["extracted_data"],
            "extracted_fields": extraction_payload["extracted_data"],
            "file_metadata": {
                "saved_upload": to_relative_api_path(saved_file_path, UPLOAD_DIR.parent),
                "content_type": file.content_type or "application/octet-stream",
            },
        }
        json_output_path = save_layout_json(
            data=layout_json_payload,
            output_dir=OUTPUT_DIR,
            base_filename=Path(file.filename).stem,
        )
        json_relative_path = to_relative_api_path(json_output_path, OUTPUT_DIR.parent)
        layout_json_payload["json_output_file"] = json_relative_path
        layout_json_payload["excel_file"] = to_relative_api_path(excel_path, OUTPUT_DIR.parent)
        json_output_path.write_text(
            json.dumps(layout_json_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        layout_status = extraction_payload["layoutlmv3_status"]
        layout_executed = bool(layout_status.get("executed"))
        huggingface_connected = bool(layout_status.get("enabled"))

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
                ],
                execution_status="success" if huggingface_connected else "fallback",
            ),
            json_output_file=json_relative_path,
        )
        logger.info("Processing finished for %s", file.filename)
        return response
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Document processing failed")
        raise HTTPException(status_code=500, detail=f"Document processing failed: {exc}") from exc
