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
};

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

  try {
    const response = await fetch("/upload", {
      method: "POST",
      body: payload,
    });

    const data = await response.json();

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

    setStatus("Document processed successfully.");
    resultSection.classList.remove("hidden");
  } catch (error) {
    setStatus(error.message || "Something went wrong while processing the upload.", true);
  } finally {
    submitButton.disabled = false;
  }
});
