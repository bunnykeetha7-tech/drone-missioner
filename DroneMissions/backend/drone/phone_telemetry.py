"""Legacy optional browser-sensor demo; never selected as a drone source.

These phone readings are not flight-controller telemetry. The GCS dashboard
uses only SimulationDrone or the fail-closed real-drone adapter.
"""
from backend.main import PhoneTelemetry
