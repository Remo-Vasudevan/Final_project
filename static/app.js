const form = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");
const submitButton = document.getElementById("submit-button");
const statusBox = document.getElementById("status");
const resultSection = document.getElementById("result");

const resultFields = {
  fileName: document.getElementById("result-file-name"),
  module: document.getElementById("result-module"),
  analysisStatus: document.getElementById("result-analysis-status"),
  documentType: document.getElementById("result-document-type"),
  layoutSummary: document.getElementById("layout-summary"),
  hfSummary: document.getElementById("hf-summary"),
  duSummary: document.getElementById("du-summary"),
  jsonLink: document.getElementById("json-link"),
  excelLink: document.getElementById("excel-link"),
  reportLink: document.getElementById("report-link"),
  reportPreview: document.getElementById("structured-report-preview"),
};

const DEFAULT_REPORT_PREVIEW = "Report preview will appear here after processing.";
const LOCAL_BACKEND_ORIGIN = "http://127.0.0.1:8001";

function isLocalHost(hostname) {
  return hostname === "127.0.0.1" || hostname === "localhost";
}

function resolveApiBaseUrl() {
  const configuredOrigin = window.SMART_INVOICE_API_ORIGIN || document.body.dataset.apiOrigin;
  if (configuredOrigin) {
    return configuredOrigin.replace(/\/$/, "");
  }

  const { protocol, hostname, port, origin } = window.location;
  if (protocol.startsWith("http") && isLocalHost(hostname) && port && port !== "8001") {
    return LOCAL_BACKEND_ORIGIN;
  }

  return origin.replace(/\/$/, "");
}

function buildApiUrl(path) {
  return `${resolveApiBaseUrl()}${path}`;
}

async function parseResponsePayload(response) {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return text ? { detail: text } : {};
}

function setStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.style.background = isError ? "rgba(166, 48, 48, 0.12)" : "rgba(184, 92, 56, 0.08)";
  statusBox.style.color = isError ? "#8d1d1d" : "";
}

function setLink(element, href) {
  if (href) {
    element.href = href;
    element.classList.remove("hidden");
    return;
  }

  element.href = "#";
  element.classList.add("hidden");
}

function setReportPreview(previewText) {
  resultFields.reportPreview.textContent = previewText || "Not Detected";
}

function resetResultView() {
  setLink(resultFields.jsonLink, "");
  setLink(resultFields.excelLink, "");
  setLink(resultFields.reportLink, "");
  resultFields.reportPreview.textContent = DEFAULT_REPORT_PREVIEW;
}

function syncApiLinks() {
  const docsLink = document.querySelector('a[href="/docs"]');
  if (docsLink) {
    docsLink.href = buildApiUrl("/docs");
  }
}

syncApiLinks();

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const [file] = fileInput.files;
  if (!file) {
    setStatus("Choose an invoice image before submitting.", true);
    return;
  }

  const payload = new FormData();
  payload.append("file", file);

  submitButton.disabled = true;
  setStatus("Uploading and processing document...");
  resultSection.classList.add("hidden");
  resetResultView();

  try {
    const response = await fetch(buildApiUrl("/upload"), {
      method: "POST",
      body: payload,
    });

    const data = await parseResponsePayload(response);

    if (!response.ok) {
      throw new Error(data.detail || data.message || "Upload failed.");
    }

    resultFields.fileName.textContent = data.file_name || "-";
    resultFields.module.textContent = data.module_name || "-";
    resultFields.analysisStatus.textContent = data.document_layout_analysis_status || "-";
    resultFields.documentType.textContent = data.json_output?.document_type || "-";
    resultFields.layoutSummary.textContent = data.layoutlmv3_summary || "-";
    resultFields.hfSummary.textContent = data.huggingface_summary || "-";
    resultFields.duSummary.textContent = data.document_understanding_summary || "-";

    setLink(resultFields.jsonLink, data.json_output_url);
    setLink(resultFields.excelLink, data.excel_file_url);
    setLink(resultFields.reportLink, data.text_report_url);
    setReportPreview(data.text_report_preview);

    setStatus("Document processed successfully.");
    resultSection.classList.remove("hidden");
  } catch (error) {
    const isNetworkError = error instanceof TypeError;
    const errorMessage = isNetworkError
      ? `Could not reach the backend at ${resolveApiBaseUrl()}. Start the API server and try again.`
      : error.message || "Something went wrong while processing the upload.";
    setStatus(errorMessage, true);
  } finally {
    submitButton.disabled = false;
  }
});
