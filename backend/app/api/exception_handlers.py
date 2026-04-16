"""Global exception handlers — enforce consistent JSON error envelope."""
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.logging import get_logger
from app.schemas.common import ErrorResponse
from app.utils.exceptions import AppException

log = get_logger("exception")


def _envelope(req: Request, status_code: int, payload: ErrorResponse) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def _handle_app(req: Request, exc: AppException):
        log.warning(
            "app_exception",
            error_code=exc.error_code,
            status=exc.status_code,
            message=exc.message,
        )
        return _envelope(
            req,
            exc.status_code,
            ErrorResponse(
                error_code=exc.error_code,
                message=exc.message,
                details=exc.details,
                request_id=getattr(req.state, "request_id", None),
                timestamp=datetime.utcnow(),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(req: Request, exc: RequestValidationError):
        errors = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")}
            for e in exc.errors()
        ]
        log.info("validation_error", errors=errors)
        return _envelope(
            req,
            422,
            ErrorResponse(
                error_code="VALIDATION_ERROR",
                message="Request validation failed",
                details={"errors": errors},
                request_id=getattr(req.state, "request_id", None),
            ),
        )

    @app.exception_handler(IntegrityError)
    async def _handle_integrity(req: Request, exc: IntegrityError):
        log.warning("db_integrity_error", error=str(exc.orig))
        return _envelope(
            req,
            409,
            ErrorResponse(
                error_code="DB_INTEGRITY_ERROR",
                message="Database constraint violation",
                request_id=getattr(req.state, "request_id", None),
            ),
        )

    @app.exception_handler(SQLAlchemyError)
    async def _handle_sqla(req: Request, exc: SQLAlchemyError):
        log.error("db_error", error=str(exc))
        return _envelope(
            req,
            500,
            ErrorResponse(
                error_code="DB_ERROR",
                message="Database error",
                request_id=getattr(req.state, "request_id", None),
            ),
        )

    @app.exception_handler(Exception)
    async def _handle_unhandled(req: Request, exc: Exception):
        # Last line of defense — never let a raw traceback leak.
        log.exception("unhandled_exception")
        return _envelope(
            req,
            500,
            ErrorResponse(
                error_code="INTERNAL_ERROR",
                message="An unexpected error occurred",
                request_id=getattr(req.state, "request_id", None),
            ),
        )
