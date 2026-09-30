(() => {
  const $ = (selector) => document.querySelector(selector);
  let state = null;
  let pitchTimer;
  let settingsTimer;
  let initialized = false;

  function render(data) {
    if (!data) return;
    state = data;
    const slider = $('#gimbalPitchSlider');
    if (!slider) return;
    slider.value = data.normalized_pitch;
    $('#gimbalPitchValue').textContent = `${Number(data.pitch).toFixed(1)}°`;
    $('#gimbalPitchTelemetry').textContent = `${Number(data.pitch).toFixed(1)}°`;
    $('#cameraPitchReadout').textContent = `PITCH ${Number(data.pitch).toFixed(1)}°`;
    $('#gimbalRoll').textContent = `${Number(data.roll).toFixed(1)}°`;
    $('#gimbalYaw').textContent = `${Number(data.yaw).toFixed(1)}°`;
    $('#gimbalMinLabel').textContent = `${data.pitch_min_degrees}° · DOWN`;
    $('#gimbalMaxLabel').textContent = `+${data.pitch_max_degrees}° · UP`;
    $('#cameraShakeToggle').checked = data.shake_enabled;
    $('#cameraShakeIntensity').value = data.shake_intensity;
    $('#shakeIntensityValue').textContent = `${Math.round(data.shake_intensity * 100)}%`;
    $('#cameraPreview').classList.toggle('shake-enabled', data.shake_enabled && data.shake_intensity > 0);
    $('#cameraPreview').style.setProperty('--shake-strength', `${data.shake_intensity}`);
    $('#cameraPreview').style.setProperty('--gimbal-pitch', `${data.pitch}deg`);
    $('#gimbalStatusText').textContent = `${data.mode} · ${data.status}`;
    $('#cameraPreview').setAttribute('aria-label', `${data.camera_status}; gimbal pitch ${Number(data.pitch).toFixed(1)} degrees`);
  }

  async function refresh() {
    if (!localStorage.getItem('dm_token') || !window.DMApi) return;
    try { render(await window.DMApi('/api/gimbal/status')); }
    catch (_) { /* The main app owns auth and API error messaging. */ }
  }

  async function savePitch(value) {
    try { render(await window.DMApi('/api/gimbal/pitch', { method: 'POST', body: JSON.stringify({ normalized_pitch: Number(value) }) })); }
    catch (error) { await refresh(); window.DMToast?.(error.message); }
  }

  async function saveSettings() {
    try {
      render(await window.DMApi('/api/gimbal/settings', { method: 'POST', body: JSON.stringify({
        shake_enabled: $('#cameraShakeToggle').checked,
        shake_intensity: Number($('#cameraShakeIntensity').value),
      }) }));
    } catch (error) { window.DMToast?.(error.message); }
  }

  function init() {
    if (initialized) { refresh(); return; }
    initialized = true;
    const slider = $('#gimbalPitchSlider');
    slider?.addEventListener('input', () => {
      const normalized = Number(slider.value);
      if (state) {
        const angle = normalized >= 0 ? normalized * state.pitch_max_degrees : normalized * Math.abs(state.pitch_min_degrees);
        render({ ...state, normalized_pitch: normalized, pitch: angle });
      }
      clearTimeout(pitchTimer);
      pitchTimer = setTimeout(() => savePitch(normalized), 140);
    });
    document.querySelectorAll('[data-gimbal-pitch]').forEach((button) => button.addEventListener('click', () => {
      const value = Number(button.dataset.gimbalPitch);
      slider.value = value;
      slider.dispatchEvent(new Event('input', { bubbles: true }));
      clearTimeout(pitchTimer);
      savePitch(value);
    }));
    $('#cameraShakeToggle')?.addEventListener('change', saveSettings);
    $('#cameraShakeIntensity')?.addEventListener('input', () => {
      const intensity = Number($('#cameraShakeIntensity').value);
      $('#shakeIntensityValue').textContent = `${Math.round(intensity * 100)}%`;
      $('#cameraPreview').style.setProperty('--shake-strength', `${intensity}`);
      clearTimeout(settingsTimer);
      settingsTimer = setTimeout(saveSettings, 160);
    });
    refresh();
  }

  window.DroneGimbal = { init, refresh, render };
  if (localStorage.getItem('dm_token')) init();
})();
