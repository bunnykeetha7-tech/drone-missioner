(() => {
  const fmt = (v, digits=1) => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v)) ? Number(v).toFixed(digits) : 'N/A';
  function render(t) {
    if (!t) return;
    const battery = t.battery || {};
    const hasGPS = Number.isFinite(t.latitude) && Number.isFinite(t.longitude);
    const put = (id, value) => { const el=document.getElementById(id); if(el) el.textContent=value; };
    const html = (id, value) => { const el=document.getElementById(id); if(el) el.innerHTML=value; };
    html('alt', `${fmt(t.altitude)} <small>m</small>`);
    html('speed', `${fmt(t.ground_speed)} <small>m/s</small>`);
    html('battery', `${fmt(battery.percentage,0)} <small>%</small>`);
    put('batteryNote', `${fmt(battery.voltage)} V · ${fmt(battery.current)} A`);
    put('flightMode', t.flight_mode || '—'); put('armState', t.armed ? 'ARMED' : 'DISARMED');
    put('lat', hasGPS ? Number(t.latitude).toFixed(6) : 'Unavailable'); put('lon', hasGPS ? Number(t.longitude).toFixed(6) : 'Unavailable');
    put('headingVal', t.heading == null ? 'N/A' : String(Math.round(t.heading)));
    put('voltage', `${fmt(battery.voltage)} V`); put('current', `${fmt(battery.current)} A`);
    put('satellites', t.gps_satellites == null ? 'N/A' : String(t.gps_satellites)); put('gpsAccuracy',t.gps_accuracy==null?'Unavailable':`${fmt(t.gps_accuracy)} m`);
    put('gpsTop', t.gps_satellites > 0 ? `${t.gps_satellites} SAT` : 'NO GPS DATA');
    put('batTop', `${fmt(battery.percentage,0)}%`);
    put('roll', `${fmt(t.roll)}°`); put('pitch', `${fmt(t.pitch)}°`); put('yaw', `${fmt(t.yaw ?? t.heading)}°`);
    put('attText', `R ${fmt(t.roll)}° · P ${fmt(t.pitch)}° · Y ${fmt(t.yaw ?? t.heading)}°`);
    put('tel-alt', `${fmt(t.altitude)} m`); put('tel-speed', `${fmt(t.ground_speed)} m/s`); put('tel-heading', t.heading == null ? 'N/A' : `${Math.round(t.heading)}°`); put('tel-sats', t.gps_satellites == null ? 'N/A' : String(t.gps_satellites));
    put('dataSourceTag', String(t.source || 'simulation').toUpperCase());
  }
  window.DashboardTelemetry = { render };
})();
