Company aircraft integration checklist

Before writing an adapter identify: manufacturer/model; flight controller; firmware; protocol; serial/UDP/TCP connection and parameters; telemetry format; SDK/API and version; authentication; vendor simulator/SITL; expected heartbeat; failsafe and company bench/flight procedure.

Implement the shared async interface. Map actual measured fields, preserve source=REAL DRONE, report unavailable measurements as unavailable, and read device parameters distinctly from JSON local defaults. Add SITL tests before bench tests. Check connection and heartbeat, telemetry, parameter read, mission download/upload, then commands under company procedure. Do not enable flight controls based only on a socket connection.
