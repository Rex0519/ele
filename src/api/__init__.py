from fastapi import APIRouter

from .devices import router as devices_router
from .electric import router as electric_router
from .alerts import router as alerts_router

api_router = APIRouter(prefix="/api")
api_router.include_router(devices_router)
api_router.include_router(electric_router)
api_router.include_router(alerts_router)

__all__ = ["api_router"]
