import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

class TelemetryBroadcaster:
    """Fan out state changes to the existing telemetry WebSocket clients."""
    def __init__(self):
        self.clients = set()

    async def broadcast(self, message):
        stale = []
        for client in tuple(self.clients):
            try:
                await client.send_json(message)
            except Exception:
                stale.append(client)
        for client in stale:
            self.clients.discard(client)

telemetry_broadcaster = TelemetryBroadcaster()

def build_websocket_router(source_getter, simulator, load_config):
    router = APIRouter()

    @router.websocket('/ws/telemetry')
    async def telemetry_stream(ws: WebSocket):
        await ws.accept()
        telemetry_broadcaster.clients.add(ws)
        try:
            while True:
                src = source_getter()
                telemetry = await src.get_telemetry()
                await ws.send_json({'telemetry': telemetry, 'status': await src.get_status(), 'track': simulator.track, 'mission_index': simulator.index})
                interval = max(0.2, float(load_config('simulation.json').get('telemetry_interval', 1)))
                await asyncio.sleep(interval)
        except WebSocketDisconnect:
            return
        finally:
            telemetry_broadcaster.clients.discard(ws)

    return router
