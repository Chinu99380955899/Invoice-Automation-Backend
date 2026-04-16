"""Typed application exceptions.

The API layer maps these to HTTP responses in a single global handler,
ensuring a consistent error envelope and preventing raw tracebacks from
leaking to clients.
"""
from typing import Any, Dict, Optional


class AppException(Exception):
    """Base class for all application exceptions."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    default_message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details or {}
        super().__init__(self.message)


# --- 4xx ---
class ValidationError(AppException):
    status_code = 422
    error_code = "VALIDATION_ERROR"
    default_message = "Validation failed."


class InvalidCredentialsError(AppException):
    status_code = 401
    error_code = "INVALID_CREDENTIALS"
    default_message = "Invalid credentials."


class NotAuthenticatedError(AppException):
    status_code = 401
    error_code = "NOT_AUTHENTICATED"
    default_message = "Authentication required."


class ForbiddenError(AppException):
    status_code = 403
    error_code = "FORBIDDEN"
    default_message = "You do not have permission to perform this action."


class NotFoundError(AppException):
    status_code = 404
    error_code = "NOT_FOUND"
    default_message = "Resource not found."


class ConflictError(AppException):
    status_code = 409
    error_code = "CONFLICT"
    default_message = "Resource conflict."


class DuplicateInvoiceError(ConflictError):
    error_code = "DUPLICATE_INVOICE"
    default_message = "This invoice has already been uploaded."


class UnsupportedFileTypeError(AppException):
    status_code = 415
    error_code = "UNSUPPORTED_FILE_TYPE"
    default_message = "The uploaded file type is not supported."


class FileTooLargeError(AppException):
    status_code = 413
    error_code = "FILE_TOO_LARGE"
    default_message = "The uploaded file is too large."


# --- 5xx ---
class OCRFailureError(AppException):
    status_code = 502
    error_code = "OCR_FAILURE"
    default_message = "OCR extraction failed."


class IntegrationError(AppException):
    status_code = 502
    error_code = "INTEGRATION_ERROR"
    default_message = "External integration failed."


class StorageError(AppException):
    status_code = 500
    error_code = "STORAGE_ERROR"
    default_message = "Storage backend operation failed."
