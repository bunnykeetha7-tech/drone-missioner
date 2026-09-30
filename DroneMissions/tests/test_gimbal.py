import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
import backend.main as backend


class GimbalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(backend.app)

    def setUp(self):
        backend.os.environ['DATA_SOURCE'] = 'simulation'
        backend.simulator.connected = False
        backend.simulator.reset()
        backend.gimbal.reset()
        login = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
        self.headers = {'Authorization': 'Bearer ' + login.json()['access_token']}

    def test_json_configured_limits_pitch_conversion_and_center(self):
        limits = backend.loadj('gimbal.json')
        for normalized, expected in [(-1, limits['pitch_min_degrees']), (0, 0), (1, limits['pitch_max_degrees'])]:
            response = self.client.post('/api/gimbal/pitch', headers=self.headers, json={'normalized_pitch': normalized})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['pitch'], expected)
            self.assertEqual(response.json()['normalized_pitch'], normalized)

    def test_pitch_and_settings_reject_out_of_range_or_non_finite(self):
        for value in [-1.01, 1.01, 'NaN']:
            response = self.client.post('/api/gimbal/pitch', headers=self.headers, json={'normalized_pitch': value})
            self.assertIn(response.status_code, (422, 400))
        response = self.client.post('/api/gimbal/settings', headers=self.headers, json={'shake_intensity': 1.1})
        self.assertEqual(response.status_code, 422)

    def test_shake_settings_and_both_reset_paths(self):
        changed = self.client.post('/api/gimbal/settings', headers=self.headers, json={'shake_enabled': False, 'shake_intensity': 0.8})
        self.assertFalse(changed.json()['shake_enabled'])
        self.assertEqual(changed.json()['shake_intensity'], 0.8)
        self.client.post('/api/gimbal/pitch', headers=self.headers, json={'normalized_pitch': -0.5})
        reset = self.client.post('/api/telemetry/reset', headers=self.headers)
        config = backend.loadj('gimbal.json')
        self.assertEqual(reset.json()['gimbal']['normalized_pitch'], config['default_normalized_pitch'])
        self.assertEqual(reset.json()['gimbal']['shake_enabled'], config['default_shake_enabled'])
        self.assertEqual(reset.json()['gimbal']['shake_intensity'], config['default_shake_intensity'])
        self.client.post('/api/gimbal/pitch', headers=self.headers, json={'normalized_pitch': 1})
        direct = self.client.post('/api/gimbal/reset', headers=self.headers)
        self.assertEqual(direct.json()['normalized_pitch'], config['default_normalized_pitch'])

    def test_gimbal_is_independent_from_legacy_drone_telemetry(self):
        demo = json.loads((ROOT / 'config' / 'demo_telemetry.json').read_text(encoding='utf-8'))
        self.client.post('/api/telemetry/import', headers=self.headers, json=demo)
        before = self.client.get('/api/drone/telemetry', headers=self.headers).json()
        changed = self.client.post('/api/gimbal/pitch', headers=self.headers, json={'normalized_pitch': 0.75})
        after = self.client.get('/api/drone/telemetry', headers=self.headers).json()
        for field in ('latitude', 'longitude', 'altitude', 'ground_speed', 'heading', 'battery', 'flight_mode', 'armed', 'gps_satellites'):
            self.assertEqual(after[field], before[field], field)
        self.assertAlmostEqual(changed.json()['pitch'], 33.75)
        self.assertNotIn('gimbal', after)

    def test_routes_require_auth_and_frontend_includes_independent_camera_module(self):
        self.assertEqual(self.client.get('/api/gimbal/status').status_code, 401)
        page = self.client.get('/').text
        self.assertIn('SIMULATED CAMERA', page)
        self.assertIn('NO LIVE VIDEO SOURCE', page)
        self.assertIn('/static/js/gimbal.js', page)
        self.assertIn('gimbal controls do not change drone telemetry', page.lower())
        self.assertEqual(self.client.get('/static/js/gimbal.js').status_code, 200)


if __name__ == '__main__':
    unittest.main()
