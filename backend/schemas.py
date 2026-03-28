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
    json_output_file: str | None = None
