import asyncio
import math

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.services.elevation import get_elevation


def build_map_router(auth_dependency):
    router = APIRouter(prefix="/api/map", tags=["map"])

    @router.get("/elevation")
    async def elevation(
        latitude: float = Query(..., ge=-90, le=90),
        longitude: float = Query(..., ge=-180, le=180),
        _user=Depends(auth_dependency),
    ):
        if not math.isfinite(latitude) or not math.isfinite(longitude):
            raise HTTPException(422, "Coordinates must be finite numbers")
        try:
            altitude = await asyncio.to_thread(get_elevation, latitude, longitude)
        except Exception as exc:
            raise HTTPException(503, "Elevation service unavailable") from exc
        return {"latitude": latitude, "longitude": longitude, "altitude": altitude}

    return router
