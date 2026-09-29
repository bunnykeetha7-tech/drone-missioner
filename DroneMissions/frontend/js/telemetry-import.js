(() => {
  function init(api, toast, onTelemetry) {
    const picker = document.getElementById('telemetryJsonFile');
    const trigger = document.getElementById('importTelemetryBtn');
    if (!picker || !trigger) return;
    trigger.addEventListener('click', () => picker.click());
    picker.addEventListener('change', async () => {
      const file = picker.files?.[0]; if (!file) return;
      if (!file.name.toLowerCase().endsWith('.json')) { toast('Select a .json telemetry file.'); picker.value=''; return; }
      let payload;
      try { payload = JSON.parse(await file.text()); }
      catch { toast('Invalid JSON file.'); picker.value=''; return; }
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)) { toast('Invalid telemetry format.'); picker.value=''; return; }
      const battery = payload.battery;
      if (battery && typeof battery !== 'object') { toast('Invalid telemetry format.'); picker.value=''; return; }
      if (battery?.percentage != null && (!Number.isFinite(Number(battery.percentage)) || Number(battery.percentage) < 0 || Number(battery.percentage) > 100)) { toast('Battery percentage must be between 0 and 100.'); picker.value=''; return; }
      try {
        const result = await api('/api/telemetry/import', { method: 'POST', body: JSON.stringify(payload) });
        toast(result.message || 'Telemetry JSON imported successfully.');
        onTelemetry?.(result.telemetry, result);
      } catch (error) { const message=String(error.message||''); toast(message.toLowerCase().includes('fetch')?'Unable to connect to backend.':message||'Invalid telemetry format.'); }
      finally { picker.value=''; }
    });
  }
  window.TelemetryImport = { init };
})();
