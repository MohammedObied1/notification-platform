from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base application exception carrying an HTTP status code."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: str = "Bad request"

    def __init__(self, detail: str | None = None) -> None:
        if detail:
            self.detail = detail
        super().__init__(self.detail)


class NotFoundError(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"


class ConflictError(AppException):
    status_code = status.HTTP_409_CONFLICT
    detail = "Resource already exists"


class UnauthorizedError(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Could not validate credentials"


class ForbiddenError(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "You do not have permission to perform this action"


class RateLimitError(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "Too many requests"


class IdempotencyConflictError(AppException):
    status_code = status.HTTP_409_CONFLICT
    detail = "Idempotency key was already used with a different request body"


# Domain errors anticipated by the roadmap (notifications/templates/webhooks) but not raised by
# any code yet — defined now so later steps don't need to touch this file's shape, only add to it.
class InvalidTemplateError(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "Template is invalid or missing required variables"


class ProviderError(AppException):
    status_code = status.HTTP_502_BAD_GATEWAY
    detail = "Notification provider error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=headers)
