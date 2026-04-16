"""FastAPI application factory."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.exception_handlers import register_exception_handlers
from app.api.middleware import RequestContextMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("app_start", env=settings.app_env, version="1.0.0")
    # Seed an admin user in dev/test so local development "just works".
    if settings.app_env in {"development", "test"}:
        try:
            from app.db.session import SessionLocal
            from app.services.user_service import UserService

            with SessionLocal() as db:
                UserService(db).ensure_seed_admin()
            log.info("seed_admin_ensured")
        except Exception as exc:
            log.warning("seed_admin_failed", error=str(exc))
    yield
    log.info("app_stop")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Production-grade Invoice Automation API",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        lifespan=lifespan,
    )

    # --- Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-request-id", "x-process-time-ms"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(RequestContextMiddleware)

    # --- Exception handlers ---
    register_exception_handlers(app)

    # --- Routes ---
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # --- Observability ---
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    return app


app = create_app()
