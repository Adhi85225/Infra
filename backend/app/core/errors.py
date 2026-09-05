"""Application error types and the handlers that render them.

All errors leave the API in one consistent envelope::

    {"error": {"code": "invalid_credentials", "message": "...", "details": {...}}}

Client code can branch on ``code``; ``message`` is safe to show to a user.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for every error the application raises deliberately."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    message: str = "The request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or {}
        self.headers = headers
        super().__init__(self.message)

    def to_response(self) -> JSONResponse:
        body: dict[str, Any] = {"error": {"code": self.code, "message": self.message}}
        if self.details:
            body["error"]["details"] = self.details
        return JSONResponse(status_code=self.status_code, content=body, headers=self.headers)


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"
    message = "The submitted data is invalid."


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"
    message = "Authentication is required."


class InvalidCredentialsError(AuthenticationError):
    code = "invalid_credentials"
    # Deliberately identical for unknown-email and wrong-password so the
    # endpoint cannot be used to enumerate accounts.
    message = "Invalid email or password."


class AccountInactiveError(AuthenticationError):
    code = "account_inactive"
    message = "This account is not active. Contact an administrator."


class AccountLockedError(AuthenticationError):
    code = "account_locked"
    message = "This account is temporarily locked due to failed sign-in attempts."


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"
    message = "You do not have permission to perform this action."


class PasswordChangeRequiredError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "password_change_required"
    message = "You must change your password before continuing."


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "The requested resource was not found."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "The request conflicts with the current state of the resource."


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "Too many requests. Please try again later."


class CSRFError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "csrf_failed"
    message = "CSRF validation failed."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return exc.to_response()

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, str] = {}
        for err in exc.errors():
            location = ".".join(str(part) for part in err["loc"] if part != "body")
            fields[location or "body"] = err["msg"]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "The submitted data is invalid.",
                    "details": {"fields": fields},
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {401: "unauthenticated", 403: "permission_denied", 404: "not_found", 405: "method_not_allowed"}
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": codes.get(exc.status_code, "http_error"),
                    "message": str(exc.detail),
                }
            },
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internals to the client; the detail goes to the log only.
        logger.exception(
            "Unhandled exception", extra={"path": request.url.path, "method": request.method}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                }
            },
        )
