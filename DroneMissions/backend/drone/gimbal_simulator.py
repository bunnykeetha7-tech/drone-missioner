"""Independent, simulation-only camera gimbal state."""
import math
import threading


class GimbalSimulator:
    def __init__(self, load_config):
        self.load_config = load_config
        self._lock = threading.RLock()
        self.reset()

    def _config(self):
        config = self.load_config('gimbal.json')
        low = config.get('pitch_min_degrees')
        high = config.get('pitch_max_degrees')
        if (isinstance(low, bool) or isinstance(high, bool) or
                not isinstance(low, (int, float)) or not isinstance(high, (int, float)) or
                not math.isfinite(low) or not math.isfinite(high) or low >= 0 or high <= 0):
            raise ValueError('gimbal pitch limits must be finite, with minimum below zero and maximum above zero')
        default = config.get('default_normalized_pitch', 0)
        intensity = config.get('default_shake_intensity', 0.35)
        if isinstance(default, bool) or not isinstance(default, (int, float)) or not math.isfinite(default) or not -1 <= default <= 1:
            raise ValueError('default gimbal pitch must be between -1 and +1')
        if isinstance(intensity, bool) or not isinstance(intensity, (int, float)) or not math.isfinite(intensity) or not 0 <= intensity <= 1:
            raise ValueError('default shake intensity must be between 0 and 1')
        return config

    def reset(self):
        config = self._config()
        with self._lock:
            self.normalized_pitch = float(config['default_normalized_pitch'])
            self.shake_enabled = bool(config.get('default_shake_enabled', True))
            self.shake_intensity = float(config.get('default_shake_intensity', 0.35))
        return self.status()

    def set_pitch(self, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not -1 <= value <= 1:
            raise ValueError('normalized_pitch must be a finite number between -1 and +1')
        self._config()
        with self._lock:
            self.normalized_pitch = float(value)
        return self.status()

    def set_settings(self, shake_enabled=None, shake_intensity=None):
        if shake_enabled is not None and not isinstance(shake_enabled, bool):
            raise ValueError('shake_enabled must be a boolean')
        if shake_intensity is not None and (isinstance(shake_intensity, bool) or not isinstance(shake_intensity, (int, float)) or not math.isfinite(shake_intensity) or not 0 <= shake_intensity <= 1):
            raise ValueError('shake_intensity must be a finite number between 0 and 1')
        with self._lock:
            if shake_enabled is not None:
                self.shake_enabled = shake_enabled
            if shake_intensity is not None:
                self.shake_intensity = float(shake_intensity)
        return self.status()

    def status(self):
        config = self._config()
        with self._lock:
            normalized = self.normalized_pitch
            pitch = (config['pitch_max_degrees'] * normalized if normalized >= 0
                     else abs(config['pitch_min_degrees']) * normalized)
            return {
                'camera_mode': 'SIMULATION',
                'camera_status': 'SIMULATED CAMERA · NO LIVE VIDEO SOURCE',
                'status': 'SIMULATION',
                'mode': 'STABILIZED',
                'normalized_pitch': normalized,
                'pitch': round(pitch, 2),
                'roll': 0.0,
                'yaw': 0.0,
                'pitch_min_degrees': config['pitch_min_degrees'],
                'pitch_max_degrees': config['pitch_max_degrees'],
                'shake_enabled': self.shake_enabled,
                'shake_intensity': self.shake_intensity,
            }
