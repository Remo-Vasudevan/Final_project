from __future__ import annotations

from typing import Iterable

from fastapi import Request, UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile

try:
    from .config import UPLOAD_FIELD_ALIASES
    from .errors import technical_http_error
    from .utils import normalize_identifier, validate_uploaded_file
except ImportError:
    from config import UPLOAD_FIELD_ALIASES
    from errors import technical_http_error
    from utils import normalize_identifier, validate_uploaded_file


def _normalize_names(values: Iterable[str]) -> set[str]:
    return {normalize_identifier(value) for value in values if normalize_identifier(value)}


def _reject_query_parameters(request: Request) -> None:
    if request.query_params:
        raise technical_http_error("Unexpected input parameter", error_code="unexpected_parameter")


async def extract_uploaded_file(request: Request) -> UploadFile:
    _reject_query_parameters(request)

    form = await request.form()
    allowed_names = _normalize_names(UPLOAD_FIELD_ALIASES)
    matching_uploads: list[UploadFile] = []
    unexpected_keys: list[str] = []

    for raw_key, raw_value in form.multi_items():
        normalized_key = normalize_identifier(raw_key)
        if normalized_key not in allowed_names:
            unexpected_keys.append(str(raw_key))
            continue

        if not isinstance(raw_value, (UploadFile, StarletteUploadFile)):
            raise technical_http_error("Unsupported input keyword", error_code="unsupported_input")

        matching_uploads.append(raw_value)

    if unexpected_keys:
        raise technical_http_error("Unexpected input parameter", error_code="unexpected_parameter")

    if len(matching_uploads) != 1:
        raise technical_http_error("Invalid field name", error_code="invalid_field_name")

    upload = matching_uploads[0]
    validate_uploaded_file(upload)
    return upload
