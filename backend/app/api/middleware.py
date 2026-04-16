"""Custom middleware: request ID, logging context, safety net."""
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logging import bind_request_context, clear_request_context, get_logger

log = get_logger("http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request_id to every request and log start/end."""

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = req_id
        bind_request_context(
            request_id=req_id,
            method=request.method,
            path=request.url.path,
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Unhandled — let the global exception handler craft the response
            log.exception("unhandled_exception")
            raise
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            log.info(
                "http_request",
                status=getattr(locals().get("response"), "status_code", 500),
                duration_ms=elapsed_ms,
            )
            clear_request_context()

        response.headers["x-request-id"] = req_id
        response.headers["x-process-time-ms"] = str(elapsed_ms)
        return response
