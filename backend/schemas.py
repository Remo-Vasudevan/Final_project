from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class APIStatusResponse(BaseModel):
    status: Literal["success", "error"]
    message: str


class HealthResponse(APIStatusResponse):
    docs_url: str


class ExtractedData(BaseModel):
    invoice_number: str = Field(default="Not found")
    invoice_date: str = Field(default="Not found")
    vendor_name: str = Field(default="Not found")
    total_amount: str = Field(default="Not found")
    tax_amount: str = Field(default="Not found")
    address: str = Field(default="Not found")
    phone_number: str = Field(default="Not found")


class LayoutLMSummary(BaseModel):
    model_name: str
    token_count: int
    embedding_preview: list[float]
    note: str


class LayoutLMv3Status(BaseModel):
    enabled: bool
    source: str
    mode: str
    model_name: str | None = None
    executed: bool | None = None
    fallback_used: bool | None = None
    note: str | None = None


class ImageSize(BaseModel):
    width: int
    height: int


class OCRLayoutData(BaseModel):
    full_text: str
    words: list[str]
    bounding_boxes: list[list[int]]
    normalized_boxes: list[list[int]]


class UploadResponse(APIStatusResponse):
    file_name: str
    document_type: str
    extracted_data: ExtractedData
    excel_file: str
    raw_text: str
    confidence_note: str
    layoutlm_summary: LayoutLMSummary
    saved_upload: str
    image_size: ImageSize | None = None
    ocr_layout_data: OCRLayoutData | None = None
    layoutlmv3_status: LayoutLMv3Status | None = None
    json_output_file: str | None = None
    text_report_file: str | None = None
    text_report_preview: str | None = None


class ModuleJsonOutput(BaseModel):
    module: str
    document_type: str
    features_used: list[str]
    execution_status: str


class PublicUploadResponse(APIStatusResponse):
    file_name: str
    module_name: str
    layoutlmv3_summary: str
    huggingface_summary: str
    document_understanding_summary: str
    json_output: ModuleJsonOutput
    json_output_file: str | None = None
    json_output_url: str | None = None
    excel_file: str | None = None
    excel_file_url: str | None = None
    text_report_file: str | None = None
    text_report_url: str | None = None
    text_report_preview: str | None = None
    document_layout_analysis_status: str | None = None
    root_url: str | None = None
    docs_url: str | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "success",
                "message": "Document processed successfully",
                "file_name": "dummy_invoice_layoutlmv3_test.png",
                "module_name": "LayoutLMv3 and Hugging Face Document Understanding Module",
                "layoutlmv3_summary": "LayoutLMv3 analyzed OCR-extracted text together with bounding box positions for layout-aware document understanding.",
                "huggingface_summary": "The model was accessed through Hugging Face and executed successfully.",
                "document_understanding_summary": "The module used spatial text positions and layout-aware contextual structure to support invoice understanding.",
                "json_output": {
                    "module": "LayoutLMv3 + Hugging Face",
                    "document_type": "invoice",
                    "features_used": [
                        "layout-aware text understanding",
                        "bounding box analysis",
                        "OCR text alignment",
                        "document structure interpretation"
                    ],
                    "execution_status": "success"
                },
                "json_output_file": "outputs/dummy_invoice_layout_data.json",
                "json_output_url": "http://127.0.0.1:8001/outputs/dummy_invoice_layout_data.json",
                "excel_file": "outputs/dummy_invoice_20260402_094500.xlsx",
                "excel_file_url": "http://127.0.0.1:8001/outputs/dummy_invoice_20260402_094500.xlsx",
                "text_report_file": "outputs/dummy_invoice_analysis_report_20260408_150000.txt",
                "text_report_url": "http://127.0.0.1:8001/report/dummy_invoice_analysis_report_20260408_150000.txt",
                "text_report_preview": "DOCUMENT ANALYSIS REPORT\n========================\n...",
                "document_layout_analysis_status": "success",
                "root_url": "http://127.0.0.1:8001/",
                "docs_url": "http://127.0.0.1:8001/docs"
            }
        }
    }
