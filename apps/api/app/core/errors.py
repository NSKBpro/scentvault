"""Domain errors. Services raise these; one handler maps them to HTTP."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code = 400

    def __init__(self, detail: str = "Bad request"):
        super().__init__(detail)
        self.detail = detail


class NotFound(DomainError):
    status_code = 404

    def __init__(self, what: str = "Resource"):
        super().__init__(f"{what} not found")


class Conflict(DomainError):
    status_code = 409


class Forbidden(DomainError):
    status_code = 403


class Unauthorized(DomainError):
    status_code = 401


class Invalid(DomainError):
    status_code = 422


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, Unauthorized) else None
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=headers)
