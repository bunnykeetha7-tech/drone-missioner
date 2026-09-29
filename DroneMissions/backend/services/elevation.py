"""Terrain elevation lookup. This is map context, never vehicle altitude."""
import json
import math
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def get_elevation(latitude: float, longitude: float) -> float:
    """Fetch terrain elevation in metres from Open-Meteo's public DEM API."""
    query = urlencode({"latitude": latitude, "longitude": longitude})
    request = Request(
        f"https://api.open-meteo.com/v1/elevation?{query}",
        headers={"Accept": "application/json", "User-Agent": "DroneMissions/1.0"},
    )
    with urlopen(request, timeout=7) as response:
        payload = json.loads(response.read().decode("utf-8"))
    values = payload.get("elevation")
    if not isinstance(values, list) or not values:
        raise ValueError("Elevation service returned no elevation")
    elevation = float(values[0])
    if not math.isfinite(elevation):
        raise ValueError("Elevation service returned an invalid elevation")
    return elevation
