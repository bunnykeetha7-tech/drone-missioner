import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

def build_websocket_router(source_getter, simulator, load_config):
    router = APIRouter()

    @router.websocket('/ws/telemetry')
    async def telemetry_stream(ws: WebSocket):
        await ws.accept()
        try:
            while True:
                src = source_getter()
                telemetry = await src.get_telemetry()
                await ws.send_json({'telemetry': telemetry, 'status': await src.get_status(), 'track': simulator.track, 'mission_index': simulator.index})
                interval = max(0.2, float(load_config('simulation.json').get('telemetry_interval', 1)))
                await asyncio.sleep(interval)
        except WebSocketDisconnect:
            return

    return router
