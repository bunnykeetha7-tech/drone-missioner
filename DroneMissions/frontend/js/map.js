(() => {
  let map = null, drone = null, user = null, selected = null, path = null, lastDronePoint = null, selectionRequest = 0;
  const validFix = t => Number.isFinite(t?.latitude) && Number.isFinite(t?.longitude) && Math.abs(t.latitude) <= 90 && Math.abs(t.longitude) <= 180;
  const escape = value => String(value ?? 'N/A').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = (value, digits=1) => value!==null&&value!==undefined&&value!==''&&Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : 'N/A';
  function dronePopup(t) {
    const b=t.battery||{}; const gps=validFix(t)?`${fmt(t.latitude,6)}<br>${fmt(t.longitude,6)}`:'Unavailable';
    return `<b>🚁 DRONE</b><br>Altitude: ${fmt(t.altitude)} m<br>Ground Speed: ${fmt(t.ground_speed)} m/s<br>Battery: ${fmt(b.percentage,0)}%<br>Voltage: ${fmt(b.voltage)} V<br>Current: ${fmt(b.current)} A<br>Flight Mode: ${escape(t.flight_mode)}<br>Heading: ${fmt(t.heading,0)}°<br>Status: ${t.armed?'ARMED':'DISARMED'}<br><br>GPS:<br>${gps}<br>Satellites: ${escape(t.gps_satellites)}`;
  }
  function init() {
    const centerButton = document.getElementById('currentLocationBtn');
    if (centerButton && !centerButton.dataset.locationBound) { centerButton.dataset.locationBound = 'true'; centerButton.addEventListener('click', locateUser); }
    if (!window.L || map) return;
    map = L.map('map', { zoomControl: true }).setView([0, 0], 2);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(map);
    path = L.polyline([], { color: '#43d4bd', weight: 3, opacity: .8 }).addTo(map);
    map.on('click', selectMapLocation);
  }
  async function selectMapLocation(event) {
    const latitude = event.latlng.lat, longitude = event.latlng.lng;
    const latText = latitude.toFixed(6), lonText = longitude.toFixed(6);
    const requestId = ++selectionRequest;
    const panel = document.getElementById('selectedMapLocationFields');
    const status = document.getElementById('selectedMapLocationStatus');
    if (panel) panel.innerHTML = `<span>LATITUDE <b>${latText}</b></span><span>LONGITUDE <b>${lonText}</b></span><span>ALTITUDE <b id="selectedMapAltitude">Loading...</b></span>`;
    if (status) status.textContent = 'Elevation is map terrain data and is separate from drone telemetry.';
    const popup = () => `📍 SELECTED LOCATION<br>Latitude: ${latText}<br>Longitude: ${lonText}<br>Altitude: ${document.getElementById('selectedMapAltitude')?.textContent || 'Loading...'}`;
    if (!selected) selected = L.marker([latitude, longitude], { icon: L.divIcon({ className: '', html: '<div class="selected-location-icon">📍</div>', iconSize: [30, 30], iconAnchor: [15, 25] }) }).addTo(map).bindPopup(popup());
    else selected.setLatLng([latitude, longitude]);
    selected.setPopupContent(popup()).openPopup();
    try {
      if (typeof window.DMApi !== 'function') throw new Error('API unavailable');
      const result = await window.DMApi(`/api/map/elevation?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}`);
      if (requestId !== selectionRequest) return;
      const altitude = Number(result.altitude);
      if (!Number.isFinite(altitude)) throw new Error('Invalid elevation response');
      const value = `${altitude.toFixed(1)} m`;
      const altitudeNode = document.getElementById('selectedMapAltitude');
      if (altitudeNode) altitudeNode.textContent = value;
      if (selected) selected.setPopupContent(popup());
    } catch (_) {
      if (requestId !== selectionRequest) return;
      const altitudeNode = document.getElementById('selectedMapAltitude');
      if (altitudeNode) altitudeNode.textContent = 'Unavailable';
      if (status) status.textContent = 'Elevation service unavailable. Coordinates are still shown.';
      if (selected) selected.setPopupContent(popup());
    }
  }
  function centerMap(latitude, longitude) {
    if (map && Number.isFinite(latitude) && Number.isFinite(longitude) && !lastDronePoint && !user) map.setView([latitude, longitude], 15);
  }
  function update(telemetry, track, options={}) {
    const put=(id,value)=>{const el=document.getElementById(id);if(el)el.textContent=value;};
    const b=telemetry?.battery||{}; const hasGPS=validFix(telemetry);
    put('mapDroneAltitude',`${fmt(telemetry?.altitude)} m`); put('mapDroneSpeed',`${fmt(telemetry?.ground_speed)} m/s`);
    put('mapDroneBattery',`${fmt(b.percentage,0)}%`); put('mapDroneVoltage',`${fmt(b.voltage)} V`); put('mapDroneCurrent',`${fmt(b.current)} A`); put('mapDroneMode',telemetry?.flight_mode||'N/A'); put('mapDroneHeading',`${fmt(telemetry?.heading,0)}°`);
    put('mapDroneGps',hasGPS?`${fmt(telemetry.latitude,6)}, ${fmt(telemetry.longitude,6)}`:'Unavailable');
    put('mapDroneSatellites',telemetry?.gps_satellites==null?'N/A':String(telemetry.gps_satellites));
    put('mapDroneAccuracy',telemetry?.gps_accuracy==null?'Unavailable':`${fmt(telemetry.gps_accuracy)} m`);
    if (!map) return;
    if (!validFix(telemetry)) {
      if (drone) { map.removeLayer(drone); drone = null; }
      path?.setLatLngs([]); lastDronePoint = null;
      return;
    }
    const point = [telemetry.latitude, telemetry.longitude];
    if (!drone) {
      drone = L.marker(point, { icon: L.divIcon({ className: '', html: '<div class="drone-icon">🚁</div>', iconSize: [30, 30], iconAnchor: [15, 15] }) }).addTo(map).bindPopup(dronePopup(telemetry));
      map.setView(point, 15);
    } else { drone.setLatLng(point); drone.setPopupContent(dronePopup(telemetry)); }
    if (options.centerOnDrone) map.setView(point, Math.max(map.getZoom(),15));
    const pathPoints=Array.isArray(track)?track.filter(p=>Array.isArray(p)&&p.length>=2&&p.every(Number.isFinite)):[];
    const uniquePoints=new Set(pathPoints.map(p=>`${p[0].toFixed(7)},${p[1].toFixed(7)}`));
    path?.setLatLngs(uniquePoints.size>=2?pathPoints:[]);
    lastDronePoint = point;
  }
  function clearUserLocation(message) {
    if (map && user) map.removeLayer(user); user = null;
    const fields = document.getElementById('userLocationFields'); const status = document.getElementById('userLocationStatus');
    if (fields) fields.innerHTML = '<span>LAT <b>N/A</b></span><span>LON <b>N/A</b></span><span>ACCURACY <b>N/A</b></span><span>SPEED <b>N/A</b></span><span>HEADING <b>N/A</b></span>';
    if (status) status.textContent = message;
  }
  function locateUser() {
    const status = document.getElementById('userLocationStatus');
    const fields = document.getElementById('userLocationFields');
    const button = document.getElementById('currentLocationBtn');
    if (!navigator.geolocation) { clearUserLocation('Geolocation is not supported by this browser.'); return; }
    if (status) status.textContent = 'Requesting your current location…';
    if (button) button.disabled = true;
    navigator.geolocation.getCurrentPosition(position => {
      const { latitude, longitude, accuracy, speed, heading } = position.coords;
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
        clearUserLocation('Unable to determine your current location.');
        if(button) button.disabled = false;
        return;
      }
      const point = [latitude, longitude];
      if (map && window.L) {
        if (!user) user = L.marker(point, { icon: L.divIcon({ className: '', html: '<div class="user-location-icon">📍</div>', iconSize: [30, 30], iconAnchor: [15, 25] }) }).addTo(map).bindPopup('YOUR LOCATION');
        else user.setLatLng(point);
        map.setView(point, Math.max(map.getZoom(), 15)); user.openPopup();
      }
      if (fields) {
        fields.innerHTML = `<span>LAT <b>${latitude.toFixed(6)}</b></span><span>LON <b>${longitude.toFixed(6)}</b></span><span>ACCURACY <b>±${Number.isFinite(accuracy) ? Math.round(accuracy) + ' m' : 'N/A'}</b></span><span>SPEED <b>${Number.isFinite(speed) && speed >= 0 ? speed.toFixed(1) + ' m/s' : 'N/A'}</b></span><span>HEADING <b>${Number.isFinite(heading) && heading >= 0 ? Math.round(heading) + '°' : 'N/A'}</b></span>`;
      }
      if (status) status.textContent = 'Your current location is shown separately from drone telemetry.';
      if (button) button.disabled = false;
    }, error => {
      const message = error.code === error.PERMISSION_DENIED ? 'Location permission denied.' : error.code === error.POSITION_UNAVAILABLE ? 'Unable to determine your current location.' : error.code === error.TIMEOUT ? 'Unable to determine your current location (request timed out).' : 'GPS unavailable.';
      clearUserLocation(message);
      if(button) button.disabled = false;
    }, { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 });
  }
  window.DroneMap = { init, update, locateUser, centerMap };
})();
