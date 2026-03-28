import json
import logging
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from config import API_DESCRIPTION, API_TITLE, API_VERSION, OUTPUT_DIR, UPLOAD_DIR
from extractor import build_extraction_result
from schemas import APIStatusResponse, HealthResponse, UploadResponse
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


@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
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
            "file_name": file.filename,
            "image_size": extraction_payload["image_size"],
            "ocr_layout_data": extraction_payload["ocr_layout_data"],
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
        json_output_path.write_text(
            json.dumps(layout_json_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        response = UploadResponse(
            status="success",
            message="Document processed successfully",
            file_name=file.filename,
            document_type=extraction_payload["document_type"],
            extracted_data=extraction_payload["extracted_data"],
            excel_file=to_relative_api_path(excel_path, OUTPUT_DIR.parent),
            raw_text=extraction_payload["raw_text"],
            confidence_note=extraction_payload["confidence_note"],
            layoutlm_summary=extraction_payload["layoutlm_summary"],
            saved_upload=to_relative_api_path(saved_file_path, OUTPUT_DIR.parent),
            image_size=extraction_payload["image_size"],
            ocr_layout_data=extraction_payload["ocr_layout_data"],
            json_output_file=json_relative_path,
        )
        logger.info("Processing finished for %s", file.filename)
        return response
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Document processing failed")
        raise HTTPException(status_code=500, detail=f"Document processing failed: {exc}") from exc







