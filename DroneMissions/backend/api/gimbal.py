from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


class PitchInput(BaseModel):
    normalized_pitch: float


class SettingsInput(BaseModel):
    shake_enabled: bool | None = None
    shake_intensity: float | None = None


def build_gimbal_router(gimbal, auth_dependency):
    router = APIRouter()

    @router.get('/api/gimbal/status')
    async def status(_user=Depends(auth_dependency)):
        return gimbal.status()

    @router.post('/api/gimbal/pitch')
    async def pitch(body: PitchInput, _user=Depends(auth_dependency)):
        try:
            return gimbal.set_pitch(body.normalized_pitch)
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @router.post('/api/gimbal/settings')
    async def settings(body: SettingsInput, _user=Depends(auth_dependency)):
        try:
            return gimbal.set_settings(body.shake_enabled, body.shake_intensity)
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @router.post('/api/gimbal/reset')
    async def reset(_user=Depends(auth_dependency)):
        try:
            return gimbal.reset()
        except ValueError as exc:
            raise HTTPException(500, f'Invalid gimbal configuration: {exc}')

    return router
