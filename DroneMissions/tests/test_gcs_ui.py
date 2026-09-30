import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
import backend.main as backend


class GCSUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(backend.app)

    def test_full_registration_is_real_backend_auth_and_email_login_works(self):
        suffix = uuid.uuid4().hex[:10]
        profile = {'full_name': 'Test Operator', 'username': 'operator_' + suffix,
                   'email': suffix + '@example.test', 'password': 'FlightSafe123'}
        registered = self.client.post('/api/auth/register', json=profile)
        self.assertEqual(registered.status_code, 200, registered.text)
        self.assertEqual(registered.json()['user']['full_name'], profile['full_name'])
        self.assertTrue(registered.json()['access_token'])
        logged_in = self.client.post('/api/auth/login', json={'username': profile['email'], 'password': profile['password']})
        self.assertEqual(logged_in.status_code, 200, logged_in.text)
        self.assertEqual(logged_in.json()['user']['username'], profile['username'])
        self.assertEqual(self.client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + logged_in.json()['access_token']}).json()['username'], profile['username'])
        duplicate = self.client.post('/api/auth/register', json=profile)
        self.assertEqual(duplicate.status_code, 409)

    def test_legacy_register_contract_and_demo_login_remain_supported(self):
        suffix = uuid.uuid4().hex[:10]
        created = self.client.post('/api/auth/register', json={'username': 'legacy_' + suffix, 'password': 'FlightSafe123'})
        self.assertEqual(created.status_code, 200, created.text)
        login = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
        self.assertEqual(login.status_code, 200)

    def test_registration_and_dashboard_pages_expose_operator_ui(self):
        registration = self.client.get('/register.html')
        self.assertEqual(registration.status_code, 200)
        for text in ('Full name', 'Username', 'Email address', 'Confirm password', 'CREATE ACCOUNT', 'openLogin'):
            self.assertIn(text, registration.text)
        dashboard = self.client.get('/').text
        for text in ('gcs-flight-panel', 'gcsHorizon', 'gcsFlightState', 'gimbalTitle', 'RESET SIMULATION', 'CURRENT LOCATION'):
            self.assertIn(text, dashboard)
        self.assertIn('uav-marker', (ROOT / 'frontend' / 'js' / 'map.js').read_text(encoding='utf-8'))
        self.assertIn('disabled title="Unavailable until the company aircraft protocol', dashboard)
        self.assertIn('/static/js/artificial-horizon.js', dashboard)

    def test_frontend_session_error_horizon_and_layout_behaviors_are_wired(self):
        app_js = (ROOT / 'frontend' / 'js' / 'app.js').read_text(encoding='utf-8')
        attitude_js = (ROOT / 'frontend' / 'js' / 'artificial-horizon.js').read_text(encoding='utf-8')
        styles = (ROOT / 'frontend' / 'css' / 'instruments.css').read_text(encoding='utf-8')
        self.assertIn("/api/auth/register", app_js)
        self.assertIn("sessionStorage.removeItem('dm_token')", app_js)
        self.assertIn('Remember', (ROOT / 'frontend' / 'index.html').read_text(encoding='utf-8'))
        self.assertIn("setProperty('--roll'", attitude_js)
        self.assertIn("setProperty('--pitch'", attitude_js)
        self.assertIn('gcs-horizon-scene', styles)
        self.assertIn('Confirm emergency simulated landing', app_js)

    def test_imported_attitude_is_retained_in_telemetry_and_reset_is_centered(self):
        login = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'}).json()
        headers = {'Authorization': 'Bearer ' + login['access_token']}
        payload = {'source': 'simulation', 'latitude': 13.0827, 'longitude': 80.2707,
                   'altitude': 20, 'ground_speed': 5, 'heading': 90,
                   'roll': 10, 'pitch': 10, 'yaw': 90, 'armed': True,
                   'flight_mode': 'LOITER', 'battery': {'percentage': 85, 'voltage': 15.8, 'current': 3.2},
                   'gps_satellites': 12}
        result = self.client.post('/api/telemetry/import', headers=headers, json=payload)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual((result.json()['telemetry']['roll'], result.json()['telemetry']['pitch']), (10, 10))
        reset = self.client.post('/api/telemetry/reset', headers=headers)
        self.assertEqual(reset.json()['telemetry']['roll'], 0)
        self.assertEqual(reset.json()['telemetry']['pitch'], 0)
        self.assertEqual(reset.json()['gimbal']['normalized_pitch'], 0)

    def test_emergency_stop_uses_existing_simulated_land_behavior(self):
        login = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'}).json()
        headers = {'Authorization': 'Bearer ' + login['access_token']}
        self.client.post('/api/drone/connect', headers=headers)
        stopped = self.client.post('/api/drone/emergency_stop', headers=headers)
        self.assertEqual(stopped.status_code, 200, stopped.text)
        self.assertEqual(stopped.json()['telemetry']['flight_mode'], 'LAND')

    def test_emergency_stop_fails_closed_for_unconfigured_physical_adapter(self):
        backend.os.environ['DATA_SOURCE'] = 'mavlink'
        login = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'}).json()
        headers = {'Authorization': 'Bearer ' + login['access_token']}
        response = self.client.post('/api/drone/emergency_stop', headers=headers)
        self.assertEqual(response.status_code, 501)
        backend.os.environ['DATA_SOURCE'] = 'simulation'


if __name__ == '__main__':
    unittest.main()
