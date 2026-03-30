import logging
from functools import lru_cache
from typing import Any

import torch
from PIL import Image
from transformers import LayoutLMv3Model, LayoutLMv3Processor

from config import LAYOUTLM_MAX_TOKENS, MODEL_NAME


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_layoutlm_components() -> tuple[LayoutLMv3Processor, LayoutLMv3Model]:
    """
    Load the base LayoutLMv3 stack once.
    This is useful for document understanding embeddings and is demo-ready.
    True field extraction from LayoutLMv3 needs a fine-tuned token-classification or QA model.
    """
    logger.info("Loading LayoutLMv3 processor and model: %s", MODEL_NAME)
    processor = LayoutLMv3Processor.from_pretrained(MODEL_NAME, apply_ocr=False)
    model = LayoutLMv3Model.from_pretrained(MODEL_NAME)
    model.eval()
    return processor, model


def _guess_document_type(raw_text: str) -> str:
    lower_text = raw_text.lower()
    if "invoice" in lower_text:
        return "invoice"
    if "receipt" in lower_text:
        return "receipt"
    if lower_text.strip():
        return "document"
    return "unknown"


def analyze_document_layout(
    image: Image.Image,
    words: list[str],
    boxes: list[list[int]],
    raw_text: str,
) -> dict[str, Any]:
    """
    Use LayoutLMv3 to create document embeddings from OCR text plus bounding boxes.
    The response is intentionally lightweight and suitable for a mini project.
    """
    if not words or not boxes:
        note = "LayoutLMv3 skipped because OCR did not produce usable words and boxes."
        return {
            "document_type": _guess_document_type(raw_text),
            "token_count": 0,
            "model_name": MODEL_NAME,
            "embedding_preview": [],
            "note": note,
            "layoutlmv3_status": {
                "enabled": True,
                "source": "Hugging Face",
                "mode": "layout-aware document understanding",
                "model_name": MODEL_NAME,
                "executed": False,
                "fallback_used": True,
                "note": note,
            },
        }

    try:
        processor, model = get_layoutlm_components()
        encoded = processor(
            images=image,
            text=words,
            boxes=boxes,
            truncation=True,
            padding="max_length",
            max_length=LAYOUTLM_MAX_TOKENS,
            return_tensors="pt",
        )

        with torch.no_grad():
            outputs = model(**encoded)

        cls_embedding = outputs.last_hidden_state[:, 0, :].squeeze(0)
        embedding_preview = [round(float(value), 4) for value in cls_embedding[:8]]
        token_count = int(encoded["attention_mask"].sum().item())
        document_type = _guess_document_type(raw_text)
        note = (
            "Base LayoutLMv3 embeddings are available. "
            "Invoice field extraction still relies on OCR + rules until a fine-tuned key-value model is added."
        )

        logger.info("LayoutLMv3 processed %s tokens", token_count)
        return {
            "document_type": document_type,
            "token_count": token_count,
            "model_name": MODEL_NAME,
            "embedding_preview": embedding_preview,
            "note": note,
            "layoutlmv3_status": {
                "enabled": True,
                "source": "Hugging Face",
                "mode": "layout-aware document understanding",
                "model_name": MODEL_NAME,
                "executed": True,
                "fallback_used": False,
                "note": note,
            },
        }
    except Exception as exc:
        logger.warning("LayoutLMv3 analysis skipped: %s", exc)
        note = (
            "LayoutLMv3 could not be loaded or executed in this environment, "
            "so the API continued with OCR + rule-based extraction only."
        )
        return {
            "document_type": _guess_document_type(raw_text),
            "token_count": len(words),
            "model_name": MODEL_NAME,
            "embedding_preview": [],
            "note": note,
            "layoutlmv3_status": {
                "enabled": False,
                "source": "Hugging Face",
                "mode": "layout-aware document understanding",
                "model_name": MODEL_NAME,
                "executed": False,
                "fallback_used": True,
                "note": note,
            },
        }
