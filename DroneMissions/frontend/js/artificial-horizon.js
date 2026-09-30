(() => {
  const put = (id, value) => {
    const node = document.getElementById(id);
    if (node) node.textContent = value;
  };
  const number = (value, digits = 1) => Number.isFinite(Number(value)) ? Number(value) : 0;
  function render(telemetry = {}, connection = {}, thresholds = {}) {
    const roll = number(telemetry.roll);
    const pitch = number(telemetry.pitch);
    const yaw = number(telemetry.yaw ?? telemetry.heading);
    const altitude = telemetry.altitude;
    const speed = telemetry.ground_speed;
    const satellites = Number(telemetry.gps_satellites) || 0;
    const fix = telemetry.latitude !== null && telemetry.latitude !== undefined && telemetry.longitude !== null && telemetry.longitude !== undefined && Number.isFinite(Number(telemetry.latitude)) && Number.isFinite(Number(telemetry.longitude));
    const horizon = document.getElementById('gcsHorizon');
    if (horizon) {
      horizon.style.setProperty('--roll', `${-roll}deg`);
      horizon.style.setProperty('--pitch', `${Math.max(-30, Math.min(30, pitch)) * 1.65}px`);
    }
    put('gcsRoll', `${roll.toFixed(1)}°`);
    put('gcsPitch', `${pitch > 0 ? '+' : ''}${pitch.toFixed(1)}°`);
    put('gcsHeading', `${String(Math.round((number(telemetry.heading) + 360) % 360).toString()).padStart(3, '0')}°`);
    put('cameraHeadingReadout', `HDG ${String(Math.round((number(telemetry.heading ?? telemetry.yaw) + 360) % 360)).padStart(3, '0')}°`);
    put('gcsYaw', `${String(Math.round((yaw + 360) % 360)).padStart(3, '0')}°`);
    put('gcsAltitude', `${Number.isFinite(Number(altitude)) ? Number(altitude).toFixed(1) : '—'} m`);
    put('gcsVerticalSpeed', `${Number.isFinite(Number(telemetry.vertical_speed)) ? `${Number(telemetry.vertical_speed) > 0 ? '+' : ''}${Number(telemetry.vertical_speed).toFixed(1)}` : '0.0'} m/s`);
    put('gcsGroundSpeed', `${Number.isFinite(Number(speed)) ? Number(speed).toFixed(1) : '—'} m/s`);
    put('gcsArmedState', telemetry.armed ? '● ARMED' : '● DISARMED');
    const flightState = document.getElementById('gcsFlightState');
    flightState?.classList.toggle('armed', !!telemetry.armed);
    const minimumSatellites = Number.isFinite(Number(thresholds.minimumSatellites)) ? Number(thresholds.minimumSatellites) : 8;
    flightState?.classList.toggle('gps-warning', !fix || satellites < minimumSatellites);
    put('gcsGpsState', fix ? `${satellites} SAT · FIX` : 'NO FIX');
    put('gcsLinkState', connection.connection_state === 'CONNECTED' || connection.connected ? 'CONNECTED' : 'DISCONNECTED');
    put('gcsFlightMode', telemetry.flight_mode || '—');
    const battery = telemetry.battery?.percentage;
    const batteryValue = Number(battery);
    const batteryText = Number.isFinite(batteryValue) ? `${Math.round(batteryValue)}%` : 'N/A';
    const lowBattery = Number.isFinite(Number(thresholds.lowBattery)) ? Number(thresholds.lowBattery) : 30;
    const criticalBattery = Number.isFinite(Number(thresholds.criticalBattery)) ? Number(thresholds.criticalBattery) : 15;
    put('gcsBatteryState', `${batteryText} · ${batteryValue <= criticalBattery ? 'CRITICAL' : batteryValue <= lowBattery ? 'LOW' : 'NORMAL'}`);
    flightState?.classList.toggle('battery-warning', Number.isFinite(batteryValue) && batteryValue <= lowBattery);
    document.getElementById('gcsAttitudeSource')?.classList.toggle('simulated', telemetry.source === 'simulation');
  }
  window.DroneAttitude = { render };
})();
