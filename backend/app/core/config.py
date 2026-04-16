"""Application configuration loaded from environment variables.

Uses pydantic-settings so every config value is validated, typed,
and never hard-coded in application code.
"""
from functools import lru_cache
from typing import List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "InvoiceAutomation"
    app_env: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    # Security
    secret_key: str = Field(default="change-me", min_length=8)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Database
    database_url: str = (
        "postgresql+psycopg2://invoice_user:invoice_pass@localhost:5432/invoice_db"
    )
    db_pool_size: int = 20
    db_max_overflow: int = 10

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_task_max_retries: int = 3
    celery_task_default_queue: str = "invoices"

    # Storage
    storage_backend: Literal["local", "azure"] = "local"
    local_storage_path: str = "./storage"
    azure_storage_connection_string: str = ""
    azure_storage_container: str = "invoices"
    max_upload_size_mb: int = 25
    allowed_extensions: str = "pdf,png,jpg,jpeg,tiff,tif"

    # Azure Document Intelligence
    azure_di_endpoint: str = ""
    azure_di_key: str = ""
    azure_di_model: str = "prebuilt-invoice"
    use_mock_azure_ocr: bool = True

    # PaddleOCR
    paddle_ocr_lang: str = "en"
    paddle_ocr_use_gpu: bool = False
    use_mock_paddle_ocr: bool = True

    # Validation
    confidence_threshold: float = 0.85
    amount_tolerance: float = 0.01
    field_match_threshold: float = 0.90

    # Integrations
    sap_api_url: str = "http://mock-sap.internal/api"
    sap_api_key: str = "mock-sap-key"
    salesforce_api_url: str = "http://mock-salesforce.internal/api"
    salesforce_api_key: str = "mock-sf-key"
    use_mock_integrations: bool = True

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    @field_validator("allowed_extensions")
    @classmethod
    def _normalize_extensions(cls, v: str) -> str:
        return ",".join(ext.strip().lower().lstrip(".") for ext in v.split(","))

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [e for e in self.allowed_extensions.split(",") if e]

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor for Settings to avoid re-parsing env vars."""
    return Settings()


settings = get_settings()
