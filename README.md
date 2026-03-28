# Smart Invoice / Document Extractor API

A modular FastAPI backend for invoice and document image understanding. The API accepts uploaded images, runs OCR to collect words and bounding boxes, sends the document through LayoutLMv3 for layout-aware processing, applies hybrid rule-based extraction for important invoice fields, and exports the final structured data to Excel.

## Features

- FastAPI backend with interactive Swagger UI
- OCR pipeline using EasyOCR with pytesseract fallback
- Bounding box normalization for LayoutLMv3 input
- LayoutLMv3 integration through Hugging Face Transformers
- Hybrid extraction using OCR text plus regex and rule-based logic
- Structured JSON response for invoice/document fields
- Excel export using pandas and openpyxl
- Auto-creates `uploads/`, `outputs/`, and `sample_data/`
- Beginner-readable project layout with comments and clear responsibilities
- GitHub-ready repository structure

## Folder Structure

```text
invoice-extractor/
|
|-- backend/
|   |-- main.py
|   |-- config.py
|   |-- extractor.py
|   |-- layoutlm_service.py
|   |-- ocr_service.py
|   |-- utils.py
|   |-- schemas.py
|   `-- requirements.txt
|
|-- uploads/
|   `-- .gitkeep
|-- outputs/
|   `-- .gitkeep
|-- sample_data/
|   `-- README.txt
|-- .gitignore
`-- README.md
```

## How It Works

1. Upload an invoice or document image to the `/upload` endpoint.
2. The backend saves the file in `uploads/`.
3. OCR extracts words, confidence scores, and bounding boxes.
4. Bounding boxes are normalized to the 0 to 1000 LayoutLM format.
5. LayoutLMv3 processes the image plus OCR tokens for layout-aware understanding.
6. Hybrid extraction logic detects invoice fields from OCR text.
7. Extracted fields are exported to an Excel file in `outputs/`.
8. OCR layout data and metadata are saved as JSON in `outputs/`.
9. The API returns structured JSON including file paths and model notes.

## Installation

### 1. Open in VS Code

Open the `invoice-extractor` folder in VS Code.

### 2. Create a virtual environment

From the project root:

```powershell
python -m venv venv
```

### 3. Activate the environment

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```cmd
venv\Scripts\activate.bat
```

macOS/Linux:

```bash
source venv/bin/activate
```

### 4. Install dependencies

```powershell
pip install -r .\backend\requirements.txt
```

## Run the Backend

From the project root:

```powershell
cd backend
..\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

Open the docs UI:

```text
http://127.0.0.1:8001/docs
```

## API Endpoints

### `GET /`
Returns a simple API status message.

### `GET /health`
Returns a health-check response.

### `POST /upload`
Uploads an invoice or document image and returns structured extracted data.

Supported file types:

- `.jpg`
- `.jpeg`
- `.png`
- `.bmp`
- `.tif`
- `.tiff`

## Example Request

Using cURL:

```bash
curl -X POST "http://127.0.0.1:8001/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@../sample_data/invoice_sample.png"
```

## Example JSON Response

```json
{
  "status": "success",
  "message": "Document processed successfully",
  "file_name": "invoice1.png",
  "document_type": "invoice",
  "image_size": {
    "width": 1400,
    "height": 1900
  },
  "ocr_layout_data": {
    "full_text": "Invoice\nABC Trading Company",
    "words": ["Invoice", "ABC", "Trading", "Company"],
    "bounding_boxes": [[80, 60, 250, 110]],
    "normalized_boxes": [[57, 31, 178, 57]]
  },
  "extracted_data": {
    "invoice_number": "INV-2026-001",
    "invoice_date": "12/03/2026",
    "vendor_name": "ABC Trading Company",
    "total_amount": "15450.00",
    "tax_amount": "2450.00",
    "address": "21 Market Road, Mumbai 400001",
    "phone_number": "+91 9876543210"
  },
  "excel_file": "outputs/invoice1_20260326_101500.xlsx",
  "json_output_file": "outputs/invoice1_layout_data_20260326_101500.json",
  "saved_upload": "uploads/6c4e5f1f2f7148249f2d140f3fb7a3b8.png",
  "raw_text": "Invoice\nABC Trading Company\nInvoice No: INV-2026-001\nDate: 12/03/2026\nTotal: 15450.00",
  "confidence_note": "Hybrid OCR + rule-based extraction with LayoutLMv3 support. Average OCR confidence: 91.42%. Base LayoutLMv3 embeddings are available. Invoice field extraction still relies on OCR + rules until a fine-tuned key-value model is added.",
  "layoutlm_summary": {
    "model_name": "microsoft/layoutlmv3-base",
    "token_count": 103,
    "embedding_preview": [0.1034, -0.2941, 0.0198, 0.2271, -0.1844, 0.0902, 0.0141, -0.0437],
    "note": "Base LayoutLMv3 embeddings are available. Invoice field extraction still relies on OCR + rules until a fine-tuned key-value model is added."
  }
}
```

## Notes

- EasyOCR is the primary OCR engine, and pytesseract is used as a fallback when EasyOCR is unavailable.
- LayoutLMv3 is used for layout-aware embeddings and document context. Exact field extraction still relies on OCR plus regex/rule logic unless a fine-tuned key-value model is added.
- On the first successful LayoutLMv3 run, Hugging Face may download model files into the local cache.

## Run Instructions in VS Code

1. Open the project root in VS Code.
2. Open a terminal in VS Code.
3. Run:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r .\backend\requirements.txt
cd backend
..\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

4. Open [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)
5. Use the `POST /upload` endpoint to test with an image from `sample_data/`
