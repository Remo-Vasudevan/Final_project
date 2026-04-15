from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


TECHNICAL_ERROR_PREFIX = "Technical Error:"


def technical_error_message(reason: str) -> str:
    clean_reason = " ".join(str(reason).split()).strip(" :")
    if not clean_reason:
        clean_reason = "Invalid request"
    return f"{TECHNICAL_ERROR_PREFIX} {clean_reason}"


def technical_http_error(
    reason: str,
    *,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    error_code: str = "technical_error",
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "message": technical_error_message(reason),
            "error_code": error_code,
        },
    )


def _normalize_http_detail(detail: Any) -> dict[str, str]:
    if isinstance(detail, dict):
        message = str(detail.get("message") or detail.get("detail") or technical_error_message("Request failed"))
        error_code = str(detail.get("error_code") or "request_error")
        return {"message": message, "error_code": error_code}

    if isinstance(detail, str):
        return {"message": detail, "error_code": "request_error"}

    return {
        "message": technical_error_message("Request failed"),
        "error_code": "request_error",
    }


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    payload = _normalize_http_detail(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": payload["message"],
            "error_code": payload["error_code"],
        },
    )


def _classify_validation_error(exc: RequestValidationError) -> tuple[str, str]:
    errors = exc.errors()
    if not errors:
        return technical_error_message("Invalid request payload"), "validation_error"

    for error in errors:
        location = error.get("loc", ())
        location_parts = [str(part).lower() for part in location]
        if "query" in location_parts:
            return technical_error_message("Unexpected input parameter"), "unexpected_parameter"
        if "path" in location_parts:
            return technical_error_message("Invalid field name"), "invalid_field_name"
        if "body" in location_parts or "form" in location_parts:
            return technical_error_message("Invalid field name"), "invalid_field_name"

    return technical_error_message("Invalid request payload"), "validation_error"


async def request_validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    message, error_code = _classify_validation_error(exc)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": message,
            "error_code": error_code,
        },
    )
