from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApiError)
    async def handle_api_error(
        request: Request,
        error: ApiError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.status_code,
            content={
                "code": error.code,
                "message": error.message,
                "details": error.details,
            },
        )
