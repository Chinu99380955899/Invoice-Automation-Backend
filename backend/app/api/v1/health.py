"""Health & readiness probes."""
from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DBSession
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health", include_in_schema=False)
def liveness() -> dict:
    return {"status": "ok", "service": settings.app_name, "env": settings.app_env}


@router.get("/ready", include_in_schema=False)
def readiness(db: DBSession) -> dict:
    checks = {"database": "ok"}
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        checks["database"] = f"error: {exc}"

    # Redis ping (non-fatal)
    try:
        import redis as _redis

        r = _redis.from_url(settings.redis_url, socket_connect_timeout=1)
        r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
