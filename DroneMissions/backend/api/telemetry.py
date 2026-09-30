from fastapi import APIRouter, Body, Depends, HTTPException
import math
from pydantic import ValidationError
from backend.schemas.telemetry import TelemetryState

def build_telemetry_router(simulator, source_getter, auth_dependency, gimbal=None):
    router = APIRouter()

    @router.post('/api/telemetry/import')
    async def import_telemetry(payload: dict = Body(...), user=Depends(auth_dependency)):
        if source_getter() is not simulator:
            raise HTTPException(409, 'Telemetry JSON import is available only in Simulation mode.')
        numeric_fields = ('latitude', 'longitude', 'altitude', 'ground_speed', 'heading', 'gps_satellites', 'gps_accuracy')
        for field in numeric_fields:
            value = payload.get(field)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))):
                raise HTTPException(400, 'Invalid telemetry format.')
        if payload.get('gps_satellites') is not None and type(payload['gps_satellites']) is not int:
            raise HTTPException(400, 'Invalid telemetry format.')
        if 'armed' in payload and not isinstance(payload['armed'], bool):
            raise HTTPException(400, 'Invalid telemetry format.')
        if 'flight_mode' in payload and payload['flight_mode'] is not None and not isinstance(payload['flight_mode'], str):
            raise HTTPException(400, 'Invalid telemetry format.')
        if 'battery' in payload:
            if not isinstance(payload['battery'], dict): raise HTTPException(400, 'Invalid telemetry format.')
            for field in ('percentage', 'voltage', 'current'):
                value = payload['battery'].get(field)
                if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))): raise HTTPException(400, 'Invalid telemetry format.')
        if 'gps' in payload and payload['gps'] is not None:
            if not isinstance(payload['gps'], dict): raise HTTPException(400, 'Invalid telemetry format.')
            for field in ('latitude', 'longitude', 'satellites', 'accuracy'):
                value = payload['gps'].get(field)
                if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))): raise HTTPException(400, 'Invalid telemetry format.')
                if field == 'satellites' and value is not None and type(value) is not int: raise HTTPException(400, 'Invalid telemetry format.')
        try:
            model = TelemetryState.model_validate(payload)
        except ValidationError as exc:
            fields = {'.'.join(str(x) for x in e['loc']) for e in exc.errors()}
            if any('battery.percentage' in f for f in fields):
                raise HTTPException(400, 'Battery percentage must be between 0 and 100.')
            if any('latitude' in f or 'longitude' in f for f in fields):
                raise HTTPException(400, 'Invalid GPS coordinates.')
            raise HTTPException(400, 'Invalid telemetry format.')
        if model.source != 'simulation':
            raise HTTPException(400, 'Only simulation telemetry JSON can be imported.')
        gps = model.gps
        lat = model.latitude if model.latitude is not None else (gps.latitude if gps else None)
        lon = model.longitude if model.longitude is not None else (gps.longitude if gps else None)
        if (lat is None) != (lon is None):
            raise HTTPException(400, 'Invalid GPS coordinates.')
        if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise HTTPException(400, 'Invalid GPS coordinates.')
        battery = model.battery
        if battery.percentage is not None and not 0 <= battery.percentage <= 100:
            raise HTTPException(400, 'Battery percentage must be between 0 and 100.')
        if not any(v is not None for v in (model.altitude, model.ground_speed, model.heading, battery.percentage, lat, lon, model.flight_mode)):
            raise HTTPException(400, 'Invalid telemetry format.')
        telemetry = simulator.import_telemetry(model)
        return {'ok': True, 'message': 'Telemetry JSON imported successfully.', 'telemetry': telemetry, 'status': await simulator.get_status(), 'track': simulator.track}

    @router.post('/api/telemetry/reset')
    async def reset_telemetry(user=Depends(auth_dependency)):
        if source_getter() is not simulator:
            raise HTTPException(409, 'Reset is available only in Simulation mode.')
        if gimbal is not None:
            gimbal.reset()
        return {'ok': True, 'telemetry': simulator.reset_simulation(), 'status': await simulator.get_status(), 'gimbal': gimbal.status() if gimbal is not None else None}

    return router
