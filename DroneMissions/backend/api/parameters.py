import copy
import json
import math
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException


def validate_parameters(value):
    if not isinstance(value, dict):
        raise HTTPException(422, "Invalid parameter configuration.")
    expected = {
        "flight": {"max_altitude", "max_speed", "default_altitude", "default_speed", "rtl_altitude"},
        "battery": {"low_battery_warning", "critical_battery"},
        "gps": {"minimum_satellites"},
        "geofence": {"enabled", "radius", "max_altitude"},
    }
    if set(value) != set(expected):
        raise HTTPException(422, "Parameter groups are missing or unknown.")
    for group, keys in expected.items():
        if not isinstance(value[group], dict) or set(value[group]) != keys:
            raise HTTPException(422, f"Parameters in {group} are missing or unknown.")
        for key, raw in value[group].items():
            name = f"{group}.{key}"
            if name == "geofence.enabled":
                if not isinstance(raw, bool):
                    raise HTTPException(422, f"Invalid value for {name}.")
            elif isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
                raise HTTPException(422, f"Invalid value for {name}.")
    f, b, g = value["flight"], value["battery"], value["geofence"]
    for name in ("max_altitude", "max_speed", "default_speed"):
        if f[name] <= 0:
            raise HTTPException(422, f"Invalid value for flight.{name}.")
    for name in ("default_altitude", "rtl_altitude"):
        if f[name] < 0 or f[name] > f["max_altitude"]:
            raise HTTPException(422, f"Invalid value for flight.{name}.")
    if f["default_speed"] > f["max_speed"]:
        raise HTTPException(422, "Invalid value for flight.default_speed.")
    if not 0 <= b["critical_battery"] <= b["low_battery_warning"] <= 100:
        raise HTTPException(422, "Battery thresholds must satisfy 0 <= critical <= warning <= 100.")
    if not 0 <= value["gps"]["minimum_satellites"] <= 60 or int(value["gps"]["minimum_satellites"]) != value["gps"]["minimum_satellites"]:
        raise HTTPException(422, "Invalid value for gps.minimum_satellites.")
    if g["radius"] <= 0:
        raise HTTPException(422, "Invalid value for geofence.radius.")
    if g["max_altitude"] < 0 or g["max_altitude"] > f["max_altitude"]:
        raise HTTPException(422, "Invalid value for geofence.max_altitude.")
    return value


def build_parameters_router(root: Path, load_config, save_config, source_getter, simulator, auth_dependency):
    router = APIRouter(tags=["parameters"])
    config_path = root / "config" / "parameters.json"
    defaults_path = root / "config" / "parameters.defaults.json"

    def require_simulation():
        if source_getter() is not simulator:
            raise HTTPException(409, "Parameter changes are disabled until a real flight-controller parameter adapter is implemented.")

    @router.get("/api/parameters")
    async def get_parameters(_user=Depends(auth_dependency)):
        p = await source_getter().get_parameters()
        return {"groups": p, "source": "JSON CONFIG" if source_getter() is simulator else "REAL DRONE", "editable": source_getter() is simulator}

    @router.put("/api/parameters/{name:path}")
    async def set_parameter(name: str, body: dict = Body(...), _user=Depends(auth_dependency)):
        require_simulation()
        current = copy.deepcopy(load_config("parameters.json"))
        parts = name.split(".")
        node = current
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                raise HTTPException(404, "Parameter not found.")
            node = node[part]
        if not parts or parts[-1] not in node:
            raise HTTPException(404, "Parameter not found.")
        node[parts[-1]] = body.get("value")
        validate_parameters(current)
        save_config("parameters.json", current)
        return {"name": name, "value": node[parts[-1]], "source": "JSON CONFIG", "groups": current}

    @router.post("/api/parameters/import")
    async def import_parameters(payload: dict = Body(...), _user=Depends(auth_dependency)):
        require_simulation()
        validate_parameters(payload)
        save_config("parameters.json", payload)
        return {"ok": True, "message": "Parameters imported successfully.", "groups": payload, "source": "JSON CONFIG"}

    @router.post("/api/parameters/reset")
    async def reset_parameters(_user=Depends(auth_dependency)):
        require_simulation()
        try:
            defaults = json.loads(defaults_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise HTTPException(500, "Default parameter configuration is unavailable.") from exc
        validate_parameters(defaults)
        save_config("parameters.json", defaults)
        return {"ok": True, "message": "Parameters reset to defaults.", "groups": defaults, "source": "JSON CONFIG"}

    return router
