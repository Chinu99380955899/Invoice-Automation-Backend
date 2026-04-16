"""Aggregate v1 router."""
from fastapi import APIRouter

from app.api.v1 import auth, health, invoices, review

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(invoices.router)
api_router.include_router(review.router)
