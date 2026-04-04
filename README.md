# Smart Invoice / Document Extractor

This repository contains a FastAPI backend and a lightweight frontend for invoice/document uploads, OCR processing, structured extraction, JSON export, and Excel export.

The project is now set up so that:
- backend startup works from the repository root
- frontend `npm install`, `npm run build`, and `npm run dev` work
- PowerShell-safe commands are provided without fragile command chaining
- Git pushes stay clean with the updated ignore rules
- deployment can run from the repository root on platforms such as Render or similar Python hosts
- optional OCR and LayoutLMv3 dependencies no longer block the backend from starting

## Final Project Structure

```text
invoice-extractor/
|-- backend/
|   |-- __init__.py
|   |-- config.py
|   |-- extractor.py
|   |-- layoutlm_service.py
|   |-- main.py
|   |-- ocr_service.py
|   |-- requirements-ml.txt
|   |-- requirements.txt
|   |-- schemas.py
|   `-- utils.py
|-- frontend/
|   |-- dist/
|   |-- index.html
|   |-- package-lock.json
|   |-- package.json
|   |-- scripts/
|   |   |-- build.mjs
|   |   `-- dev-server.mjs
|   `-- static/
|       |-- app.js
|       `-- styles.css
|-- outputs/
|   `-- .gitkeep
|-- sample_data/
|   |-- README.txt
|   `-- invoice_sample.png
|-- scripts/
|   |-- build-frontend.ps1
|   |-- run-backend.ps1
|   |-- run-frontend.ps1
|   `-- setup-backend.ps1
|-- uploads/
|   `-- .gitkeep
|-- .gitignore
|-- Procfile
|-- README.md
|-- render.yaml
|-- requirements.txt
`-- runtime.txt
```

## What Was Fixed

### Terminal execution issues
- Added PowerShell-safe helper scripts in [scripts/setup-backend.ps1](D:/layoutMv3/invoice-extractor/scripts/setup-backend.ps1), [scripts/run-backend.ps1](D:/layoutMv3/invoice-extractor/scripts/run-backend.ps1), [scripts/run-frontend.ps1](D:/layoutMv3/invoice-extractor/scripts/run-frontend.ps1), and [scripts/build-frontend.ps1](D:/layoutMv3/invoice-extractor/scripts/build-frontend.ps1)
- Standardized root-level commands so you do not need brittle `&` command chaining in the VS Code terminal

### Backend issues
- Made OCR and LayoutLMv3 imports lazy/optional in [backend/ocr_service.py](D:/layoutMv3/invoice-extractor/backend/ocr_service.py) and [backend/layoutlm_service.py](D:/layoutMv3/invoice-extractor/backend/layoutlm_service.py)
- Replaced the Excel export dependency path in [backend/utils.py](D:/layoutMv3/invoice-extractor/backend/utils.py) with a direct `openpyxl` implementation so startup is lighter and deployment is safer
- Kept FastAPI routing and upload logic intact in [backend/main.py](D:/layoutMv3/invoice-extractor/backend/main.py)

### Frontend issues
- Added a real frontend Node project in [frontend/package.json](D:/layoutMv3/invoice-extractor/frontend/package.json)
- Added a frontend build script in [frontend/scripts/build.mjs](D:/layoutMv3/invoice-extractor/frontend/scripts/build.mjs)
- Added a frontend dev server with backend proxy support in [frontend/scripts/dev-server.mjs](D:/layoutMv3/invoice-extractor/frontend/scripts/dev-server.mjs)
- Verified the frontend build output in [frontend/dist/index.html](D:/layoutMv3/invoice-extractor/frontend/dist/index.html)

### Dependency issues
- Split dependencies into:
  - base backend dependencies in [backend/requirements.txt](D:/layoutMv3/invoice-extractor/backend/requirements.txt)
  - optional advanced OCR/ML dependencies in [backend/requirements-ml.txt](D:/layoutMv3/invoice-extractor/backend/requirements-ml.txt)
- Added root [requirements.txt](D:/layoutMv3/invoice-extractor/requirements.txt) for deployment platforms that install from repo root

### Git and deployment issues
- Updated [/.gitignore](D:/layoutMv3/invoice-extractor/.gitignore) for Python, frontend, and runtime artifacts
- Added [Procfile](D:/layoutMv3/invoice-extractor/Procfile), [runtime.txt](D:/layoutMv3/invoice-extractor/runtime.txt), and [render.yaml](D:/layoutMv3/invoice-extractor/render.yaml)
- Confirmed `origin` already points to `https://github.com/Remo-Vasudevan/Final_project.git`

## Verified Checks

These checks were executed successfully:
- `python -m compileall .\backend`
- `python -c "import backend.main; print(backend.main.app.title)"`
- `npm install` inside `frontend`
- `npm run build` inside `frontend`
- backend startup on `http://127.0.0.1:8001`
- `GET /health`
- `GET /docs`
- `POST /upload` with `sample_data/invoice_sample.png`
- frontend dev server startup on `http://127.0.0.1:4173`
- frontend proxy request to backend `/health`

## PowerShell-Safe Local Setup

Open VS Code terminal at:

```powershell
D:\layoutMv3\invoice-extractor
```

### 1. Create the virtual environment if needed

```powershell
python -m venv venv
```

### 2. Install backend dependencies

```powershell
.\scripts\setup-backend.ps1
```

### 3. Install frontend dependencies

```powershell
Set-Location .\frontend
npm install
Set-Location ..
```

## Run The Backend

### Preferred command

```powershell
.\scripts\run-backend.ps1
```

### Run on a different port

```powershell
.\scripts\run-backend.ps1 -Port 8002
```

### Backend links

If you use port `8001`:
- `http://127.0.0.1:8001/`
- `http://127.0.0.1:8001/health`
- `http://127.0.0.1:8001/docs`
- `http://127.0.0.1:8001/openapi.json`

## Run The Frontend

### Preferred command

```powershell
.\scripts\run-frontend.ps1
```

### Frontend link

- `http://127.0.0.1:4173/`

The frontend dev server proxies API traffic to `http://127.0.0.1:8001` by default.

## Build The Frontend

### Preferred command

```powershell
.\scripts\build-frontend.ps1
```

### Generated build folder

- `frontend\dist\`

## Optional Advanced OCR / LayoutLMv3 Setup

If you want the richer OCR/ML stack in a compatible Python environment such as Python `3.11.x`, install:

```powershell
.\venv\Scripts\python.exe -m pip install -r .\backend\requirements-ml.txt
```

Notes:
- Base backend startup no longer depends on these packages.
- `easyocr`, `torch`, `transformers`, and `pytesseract` are optional.
- `pytesseract` still requires the Tesseract OCR system binary if you want that fallback engine available.

## Upload Test Command

With the backend running:

```powershell
curl.exe -X POST http://127.0.0.1:8001/upload -F "file=@sample_data/invoice_sample.png"
```

## GitHub Push Commands

Current branch:
- `main`

Remote:
- `origin -> https://github.com/Remo-Vasudevan/Final_project.git`

Safe push flow:

```powershell
git status
git add .
git commit -m "Stabilize backend frontend and deployment workflow"
git push origin main
```

## Deployment Steps

### Recommended deployment shape
Deploy the FastAPI backend as the main web service. It already serves the frontend at `/`, so you do not need a separate frontend deployment unless you want one.

### Render deployment
1. Push this repository to GitHub.
2. Create a new Render Web Service from the repository.
3. Render can use the included `render.yaml`, or use these values manually:

```text
Build Command: pip install -r requirements.txt
Start Command: python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

4. After deploy, open the service root URL.
5. Expected hosted links:
   - `/`
   - `/health`
   - `/docs`

### Generic Python host deployment
Use:

```text
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

## Final Verification Checklist

- backend dependencies install without errors
- frontend dependencies install without errors
- backend starts from repo root without import/path failures
- frontend dev server starts from repo root without folder confusion
- `/` opens correctly
- `/health` returns success
- `/docs` opens correctly
- upload request returns HTTP 200
- JSON output is generated in `outputs/`
- Excel output is generated in `outputs/`
- `npm run build` succeeds
- `git push origin main` works from the correct remote
- deployment installs from root `requirements.txt`
- deployed root URL opens correctly

## Expected Links

### Local
- Backend root: `http://127.0.0.1:8001/`
- Backend docs: `http://127.0.0.1:8001/docs`
- Frontend dev server: `http://127.0.0.1:4173/`

### Deployment
- Root app: `https://<your-service-domain>/`
- Health endpoint: `https://<your-service-domain>/health`
- Docs: `https://<your-service-domain>/docs`

## Notes

- The backend preserves the existing extraction flow and only hardens failure points.
- Optional OCR/ML packages can still be added later without changing the API surface.
- The easiest production model is a single FastAPI deployment serving both API and frontend.
