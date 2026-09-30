from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class BatteryTelemetry(BaseModel):
    percentage: float | None = Field(default=None, ge=0, le=100)
    voltage: float | None = Field(default=None, ge=0)
    current: float | None = Field(default=None, ge=0)

class GPSTelemetry(BaseModel):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    satellites: int | None = Field(default=None, ge=0)
    accuracy: float | None = Field(default=None, ge=0)

class TelemetryState(BaseModel):
    model_config = ConfigDict(extra='allow')
    source: Literal['simulation'] = 'simulation'
    timestamp: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    altitude: float | None = Field(default=None, ge=0)
    ground_speed: float | None = Field(default=None, ge=0)
    vertical_speed: float | None = None
    heading: float | None = Field(default=None, ge=0, lt=360)
    battery: BatteryTelemetry = Field(default_factory=BatteryTelemetry)
    gps: GPSTelemetry | None = None
    flight_mode: str | None = None
    armed: bool = False
    gps_satellites: int | None = Field(default=None, ge=0)
    gps_accuracy: float | None = Field(default=None, ge=0)
