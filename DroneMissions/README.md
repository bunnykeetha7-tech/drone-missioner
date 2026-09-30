# Drone Missions — Ground Control Station

A local-first GCS with an explicit JSON-powered simulation mode. Dashboard telemetry is sourced from the backend simulator; demo values are never loaded automatically. Real-drone mode remains fail-closed until the company aircraft protocol is identified and a tested adapter is implemented.

## Features

- FastAPI backend, responsive dashboard, JWT authentication and SQLite persistence
- Simulation mission editor, validation, upload, controls, live WebSocket telemetry, maps, charts and generated flight logs
- Dashboard Drone Connection panel with Auto Connect, explicit connection states, link/telemetry health, heartbeat, protocol and connection method
- Dashboard simulated gimbal/camera preview with configurable normalized pitch mapping and adjustable preview shake; it is not a live video feed
- Safe initial telemetry with unavailable GPS; import and reset simulation telemetry through dedicated backend routes
- Independent map-click terrain elevation lookup and browser Current Location; map coordinates, device GPS, and drone telemetry use separate markers and state
- Simulation parameter management in `config/parameters.json`
- A fail-closed real-drone adapter placeholder; no vendor or protocol is assumed

## Architecture

`Browser → FastAPI → DroneInterface → SimulationDrone | MAVLinkDrone (disabled placeholder)`

The frontend uses the same telemetry/WebSocket interfaces regardless of adapter. `DATA_SOURCE=simulation` is the default; `DATA_SOURCE=mavlink` selects the disabled adapter. Settings can switch between Simulation and Real Drone. The older phone sensor code is isolated and is not a drone data source or an option in the GCS.

The dashboard **Auto Connect** calls `POST /api/drone/auto-connect`, selects the currently available Simulation adapter, connects it, and verifies a telemetry response before displaying CONNECTED. Link quality and heartbeat are explicitly marked simulated. No validated physical adapter is configured in this project, so Auto Connect does not probe or command hardware. Manual Connect in Real Drone mode reports the adapter as unavailable rather than simulating a physical connection.

Connection telemetry health is based on backend telemetry reception, not the Connect button. A working simulator reports `RECEIVING`, `Heartbeat: OK`, `Link: GOOD`, and `Protocol: SIMULATION`; these values describe the simulator only. A missed telemetry stream reports `STALE`. Disconnect preserves simulator telemetry, missions, parameters, and browser Current Location. Auto Connect never arms or starts a flight action.

## Windows quick start

1. Install Python 3.10 or newer and enable **Add Python to PATH**.
2. Double-click `start.bat` from the extracted project folder. It creates `.venv`, installs requirements, and runs Uvicorn on `0.0.0.0:8000`.
3. Open `http://127.0.0.1:8000`; Swagger is at `http://127.0.0.1:8000/docs`. Other devices on the LAN can use the host PC's LAN address on port 8000. Only use trusted networks.
4. Demo login: **admin / admin123**.

Manual run from the project root: `python -m venv .venv`, `.venv\Scripts\activate`, `pip install -r backend\requirements.txt`, then `uvicorn backend.main:app --host 0.0.0.0 --port 8000`. SQLite creates `backend/database` automatically at startup.

## Safe initial state

Before connection or import the simulation state is altitude 0 m, speed 0 m/s, battery 100% (16.8 V, 0.0 A), STABILIZE, disarmed, heading 0°, zero satellites, and unavailable GPS. The demo telemetry file is not auto-loaded. A Simulation connection establishes simulated GPS at the configured home position; reset clears that fix again.

## Import telemetry JSON

Choose **Import Telemetry JSON** on the dashboard and select `config/demo_telemetry.json` (or another Simulation telemetry JSON file). The browser parses the file and submits it to `POST /api/telemetry/import`. FastAPI validates and normalizes it, updates the active `SimulationDrone` state, and sends it to the dashboard through the same WebSocket. Imported data stays current for the active server session and does not execute arm/takeoff/land/RTL commands or alter parameter configuration.

The normalized API shape uses `source`, timestamp, GPS coordinates, altitude, ground speed, heading, nested battery percentage/voltage/current, flight mode, armed state, satellite count, and GPS accuracy. Missing values remain null. Invalid types, GPS ranges, and battery percentage outside 0–100 are rejected.

Select **Reset Simulation** to call `POST /api/telemetry/reset`. It clears imported state and the drone marker/path and restores the safe initial values.

## Current Location vs. drone GPS

**Current Location** asks the browser for location only after the user clicks. It displays actual browser latitude, longitude, accuracy, and optional speed/heading, and adds a separate YOUR LOCATION map marker. It never sends that position to FastAPI or changes drone telemetry, simulator state, flight controls, or the drone marker. Permission denial, unavailable position, timeout, and unsupported browsers are reported without inventing values. Geolocation generally requires localhost or HTTPS.

The DRONE marker appears only when backend drone telemetry has valid coordinates. On initial startup/reset GPS is unavailable and the drone marker is absent. A Current Location fix uses a visually separate marker.

Clicking the dashboard flight map shows a separate SELECTED LOCATION marker and coordinates to six decimal places. The backend endpoint `GET /api/map/elevation?latitude=...&longitude=...` fetches terrain elevation from Open-Meteo's Elevation API using the Copernicus GLO-90 digital elevation model (about 90 m resolution). The panel immediately shows Loading and displays Unavailable if the elevation service cannot be reached. Terrain elevation describes the map location, not vehicle altitude. Attribution: [Open-Meteo Elevation API](https://open-meteo.com/en/docs/elevation-api) and the Copernicus DEM. The map elevation lookup requires internet access; it does not modify telemetry, mission state, or Current Location.

## Simulation mission workflow

Connect Simulation, open Mission Planner, create map waypoints, edit values, validate, save, upload, and start the mission. The virtual drone moves between waypoints, updates telemetry and flight path, and records a SQLite flight log. Current Location is independent and cannot affect mission coordinates.

## JSON configuration

- `config/drone.json`: identity, firmware label and simulated home position.
- `config/parameters.json`: flight limits, alert thresholds and geofence; these values drive validation.
- `config/simulation.json`: telemetry interval, movement speed, battery drain and GPS accuracy.
- `config/demo_telemetry.json`: optional dashboard telemetry import example; never automatically loaded.
- `config/missions.json`: reserved seed/import format; saved missions persist in SQLite.

Edit `config/parameters.json` and restart to load changed limits. For example, set maximum altitude and geofence maximum altitude to 50 m and validate an 80 m waypoint; it should be rejected. Telemetry import modifies only current session telemetry and never overwrites parameters.

The supplied active parameters use 50 m maximum altitude, 10 m/s maximum speed, 20 m default altitude, 5 m/s default speed, and 15 m RTL altitude. `config/parameters.defaults.json` is the reset template; the active source of truth remains `config/parameters.json`. The Parameters page imports a complete validated JSON configuration through `POST /api/parameters/import`, edits individual values through `PUT /api/parameters/{name}`, exports the current backend configuration, and resets through `POST /api/parameters/reset`. Mission waypoint defaults, mission validation, simulator speed/altitude behavior, and dashboard warnings read the active JSON configuration. Parameter writes are disabled for the unconfigured real-drone adapter.

The dashboard shows ACTIVE FLIGHT PARAMETERS fetched from `GET /api/parameters`, current telemetry separately, warnings based on current limits, and a mission status summary. The map drone marker and popup plus the DRONE TELEMETRY panel all use the same backend/WebSocket telemetry. A single GPS fix displays a marker but no flight-path line; a path appears once multiple distinct GPS positions are available.

## Real-drone integration

Before implementing an adapter, obtain the manufacturer's identity and model, flight controller, firmware, protocol, connection method, telemetry format, SDK/API, authentication requirements, SITL/simulator availability, and company hardware test procedure. `backend/drone/mavlink_interface.py` intentionally contains no working manufacturer/protocol support.

Implement and test the appropriate adapter against the common interface using the company simulator/SITL. Map only measured device data; leave unavailable fields null and mark source as real. Do not substitute simulator JSON or enable physical commands because a connection succeeded. Verify heartbeat, telemetry, parameter reads, mission download/upload, then commands under company procedure. Use appropriate bench precautions and never rely on this application as the sole flight safety system.

## Simulated camera and gimbal

The dashboard camera panel is an abstract HUD preview labeled **SIMULATED CAMERA · NO LIVE VIDEO SOURCE**. It renders no captured or fabricated live video. Its gimbal state is independent of drone telemetry and flight attitude. The pitch slider maps normalized values from -1 (down) through 0 (center) to +1 (up), using the limits in `config/gimbal.json`. Preview-only shake can be disabled or adjusted from the panel. **Reset Simulation** restores both aircraft and gimbal simulation defaults. REST endpoints are `GET /api/gimbal/status`, `POST /api/gimbal/pitch`, `POST /api/gimbal/settings`, and `POST /api/gimbal/reset`.

## API

FastAPI explorer: `/docs`. Protected routes use `Authorization: Bearer <access_token>`.

- Authentication: `POST /api/auth/login`, `/api/auth/register`; `GET /api/auth/me`
- Drone: `GET /api/drones`, `/api/drone/status`, `/api/drone/telemetry`; `POST /api/drone/{connect|disconnect|arm|disarm|takeoff|land|rtl|pause|resume|start_mission}`
- Connection: `POST /api/drone/auto-connect` (currently selects and verifies the JSON simulator)
- Parameters: `GET /api/parameters`, `PUT /api/parameters/{dotted.name}`, `POST /api/parameters/import`, `POST /api/parameters/reset`
- Telemetry: `POST /api/telemetry/import`, `/api/telemetry/reset`; WebSocket `/ws/telemetry`
- Simulated gimbal: `GET /api/gimbal/status`, `POST /api/gimbal/pitch`, `/api/gimbal/settings`, `/api/gimbal/reset`
- Map: `GET /api/map/elevation?latitude=...&longitude=...` (terrain elevation lookup)
- Missions: `GET/POST /api/missions`, `GET/PUT/DELETE /api/missions/{id}`, `POST /api/missions/{id}/validate|upload`
- Parameters: `GET /api/parameters`, `PUT /api/parameters/{dotted.name}`
- Logs/alerts: `GET /api/flights`, `GET /api/flights/{id}`, `GET /api/alerts`

## Tests and limitations

Run `python -m unittest discover -s tests` and `python -m compileall backend`. Browser map tiles need internet. A physical drone and browser geolocation hardware were not available for hardware/browser-permission testing. The demo JWT secret is not suitable for public deployment; set a strong `JWT_SECRET` and secure the service before any non-demo use.
