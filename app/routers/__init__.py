"""API router registry."""

from fastapi import APIRouter

from app.routers.analytics_costs import router as analytics_costs_router
from app.routers.analytics_rent import router as analytics_rent_router
from app.routers.health import router as health_router
from app.routers.moderation import router as moderation_router
from app.routers.submissions import router as submissions_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(analytics_rent_router, prefix="/analytics/rent", tags=["analytics-rent"])
api_router.include_router(analytics_costs_router, prefix="/analytics/costs", tags=["analytics-costs"])
api_router.include_router(submissions_router, prefix="/submissions", tags=["submissions"])
api_router.include_router(moderation_router, prefix="/moderation", tags=["moderation"])
