import json, sys, tempfile, time, unittest
from unittest.mock import AsyncMock, patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
import backend.main as backend

class Workflow(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.client=TestClient(backend.app)
 def setUp(self):
  backend.os.environ['DATA_SOURCE']='simulation'; backend.simulator.connected=False; backend.simulator.reset()
  r=self.client.post('/api/auth/login',json={'username':'admin','password':'admin123'}); self.assertEqual(r.status_code,200); self.h={'Authorization':'Bearer '+r.json()['access_token']}
 def demo(self): return json.loads((ROOT/'config'/'demo_telemetry.json').read_text(encoding='utf-8'))
 def test_map_elevation_lookup_returns_coordinate_and_terrain(self):
  with patch('backend.api.map.get_elevation',return_value=6.5):
   r=self.client.get('/api/map/elevation?latitude=13.0827&longitude=80.2707',headers=self.h)
  self.assertEqual(r.status_code,200); self.assertEqual(r.json(),{'latitude':13.0827,'longitude':80.2707,'altitude':6.5})
 def test_map_elevation_failure_is_service_unavailable(self):
  with patch('backend.api.map.get_elevation',side_effect=TimeoutError()):
   r=self.client.get('/api/map/elevation?latitude=13.0827&longitude=80.2707',headers=self.h)
  self.assertEqual(r.status_code,503); self.assertEqual(r.json()['detail'],'Elevation service unavailable')
 def test_map_elevation_validates_coordinates_and_requires_auth(self):
  self.assertEqual(self.client.get('/api/map/elevation?latitude=91&longitude=0',headers=self.h).status_code,422)
  self.assertEqual(self.client.get('/api/map/elevation?latitude=0&longitude=181',headers=self.h).status_code,422)
  self.assertEqual(self.client.get('/api/map/elevation?latitude=0&longitude=0').status_code,401)
 def test_map_click_is_separate_from_drone_and_current_location(self):
  js=(ROOT/'frontend'/'js'/'map.js').read_text(encoding='utf-8')
  html=(ROOT/'frontend'/'index.html').read_text(encoding='utf-8')
  self.assertIn("map.on('click', selectMapLocation)",js)
  self.assertIn("navigator.geolocation.getCurrentPosition",js)
  self.assertIn("/api/map/elevation?latitude=",js)
  self.assertIn("selected.setLatLng([latitude, longitude])",js)
  self.assertIn("altitudeNode.textContent = 'Unavailable'",js)
  self.assertIn('id="selectedMapLocationFields"',html)
  self.assertIn('id="currentLocationBtn"',html)
  with patch('backend.api.map.get_elevation',return_value=321.0):
   self.client.get('/api/map/elevation?latitude=12&longitude=75',headers=self.h)
  telemetry=self.client.get('/api/drone/telemetry',headers=self.h).json()
  self.assertIsNone(telemetry['latitude']); self.assertIsNone(telemetry['longitude']); self.assertEqual(telemetry['altitude'],0.0)
 def test_connection_panel_auto_connect_verifies_simulated_link(self):
  page=self.client.get('/').text
  for element in ('connectionState','autoConnectBtn','connectionConnectBtn','connectionDisconnectBtn','connectionLink','connectionTelemetry','connectionHeartbeat','connectionProtocol','connectionMethod'):
   self.assertIn(f'id="{element}"',page)
  r=self.client.post('/api/drone/auto-connect',headers=self.h)
  self.assertEqual(r.status_code,200,r.text)
  data=r.json(); self.assertEqual(data['attempted'],['SIMULATION']); self.assertTrue(data['connected'])
  self.assertTrue(data['status']['simulated']); self.assertEqual(data['status']['connection_state'],'CONNECTED')
  self.assertEqual(data['status']['telemetry_status'],'RECEIVING'); self.assertEqual(data['status']['link_quality'],'GOOD')
  self.assertEqual(data['status']['heartbeat'],'OK'); self.assertEqual(data['status']['heartbeat_source'],'SIMULATED')
  self.assertEqual(data['telemetry']['source'],'simulation')
  self.assertFalse(backend.simulator.armed); self.assertIsNone(backend.simulator.flight)
  self.assertEqual(self.client.get('/api/drone/status',headers=self.h).json()['connection_method'],'Simulation')
 def test_connection_status_reports_disconnected_and_disconnects(self):
  s=self.client.get('/api/drone/status',headers=self.h).json()
  self.assertEqual(s['connection_state'],'DISCONNECTED'); self.assertEqual(s['link_status'],'OFFLINE')
  self.assertEqual(s['telemetry_status'],'NOT RECEIVING'); self.assertIsNone(s['heartbeat_at'])
  connected=self.client.post('/api/drone/connect',headers=self.h).json(); self.assertEqual(connected['connection_state'],'CONNECTED')
  self.assertEqual(connected['telemetry_status'],'NOT RECEIVING'); self.assertEqual(connected['heartbeat'],'--')
  self.client.get('/api/drone/telemetry',headers=self.h)
  receiving=self.client.get('/api/drone/status',headers=self.h).json(); self.assertEqual(receiving['telemetry_status'],'RECEIVING'); self.assertEqual(receiving['heartbeat'],'OK')
  retained=backend.simulator.current_telemetry
  disconnected=self.client.post('/api/drone/disconnect',headers=self.h).json(); self.assertEqual(disconnected['connection_state'],'DISCONNECTED')
  self.assertEqual(disconnected['protocol'],None); self.assertEqual(disconnected['link_quality'],'OFFLINE')
  self.assertEqual(self.client.get('/api/drone/telemetry',headers=self.h).json()['altitude'],retained['altitude'])
 def test_connection_panel_frontend_supports_error_state_and_existing_controls(self):
  js=(ROOT/'frontend'/'js'/'app.js').read_text(encoding='utf-8')
  html=(ROOT/'frontend'/'index.html').read_text(encoding='utf-8')
  self.assertIn("'/api/drone/auto-connect'",js); self.assertIn("connection_state:'CONNECTING'",js); self.assertIn("connection_state:'ERROR'",js)
  for element in ('currentLocationBtn','importTelemetryBtn','resetSimulationBtn','map','missionMap'):
   self.assertIn(f'id="{element}"',html)
 def test_parameter_import_validation_reset_and_no_flight_action(self):
  path=ROOT/'config'/'parameters.json'; original=path.read_bytes()
  try:
   params=json.loads(original.decode('utf-8')); params['flight']['max_altitude']=45; params['geofence']['max_altitude']=45
   result=self.client.post('/api/parameters/import',headers=self.h,json=params)
   self.assertEqual(result.status_code,200,result.text); self.assertEqual(result.json()['groups']['flight']['max_altitude'],45)
   self.assertFalse(backend.simulator.armed); self.assertIsNone(backend.simulator.flight)
   invalid=json.loads(json.dumps(params)); invalid['flight']['max_altitude']='hello'
   response=self.client.post('/api/parameters/import',headers=self.h,json=invalid)
   self.assertEqual(response.status_code,422); self.assertIn('flight.max_altitude',response.json()['detail'])
   self.assertEqual(self.client.put('/api/parameters/flight.max_speed',headers=self.h,json={'value':-1}).status_code,422)
   reset=self.client.post('/api/parameters/reset',headers=self.h)
   self.assertEqual(reset.status_code,200); self.assertEqual(reset.json()['groups']['flight']['max_altitude'],50)
   self.assertEqual(self.client.get('/api/parameters',headers=self.h).json()['groups']['flight']['default_altitude'],20)
   self.assertFalse(backend.simulator.armed); self.assertIsNone(backend.simulator.flight)
  finally: path.write_bytes(original)
 def test_parameter_import_is_blocked_for_unconfigured_real_source(self):
  original=(ROOT/'config'/'parameters.json').read_bytes()
  try:
   self.client.post('/api/config/source',headers=self.h,json={'mode':'mavlink'})
   r=self.client.post('/api/parameters/import',headers=self.h,json=json.loads(original))
   self.assertEqual(r.status_code,409)
  finally:
   (ROOT/'config'/'parameters.json').write_bytes(original)
   backend.os.environ['DATA_SOURCE']='simulation'
 def test_parameter_export_and_invalid_values(self):
  groups=self.client.get('/api/parameters',headers=self.h).json()['groups']
  self.assertEqual(groups['flight']['max_altitude'],50)
  path=ROOT/'config'/'parameters.json'; original=path.read_bytes()
  try:
   for group,key,value in [('flight','max_speed','fast'),('gps','minimum_satellites',-5),('geofence','radius','abc'),('flight','default_altitude',-1)]:
    candidate=json.loads(original.decode('utf-8')); candidate[group][key]=value
    result=self.client.post('/api/parameters/import',headers=self.h,json=candidate)
    self.assertEqual(result.status_code,422,(group,key,result.text))
   self.assertEqual(self.client.get('/api/parameters',headers=self.h).json()['groups'],groups)
  finally: path.write_bytes(original)
 def test_dashboard_shows_common_map_telemetry_and_active_parameters(self):
  page=self.client.get('/').text
  for element in ('mapDroneAltitude','mapDroneSpeed','mapDroneBattery','mapDroneVoltage','mapDroneCurrent','mapDroneMode','mapDroneHeading','mapDroneGps','mapDroneSatellites','mapDroneAccuracy','activeMaxAltitude','activeMaxSpeed','dashboardWarnings','dashboardMissionStatus'):
   self.assertIn(f'id="{element}"',page)
  map_js=(ROOT/'frontend'/'js'/'map.js').read_text(encoding='utf-8')
  self.assertIn('function dronePopup(t)',map_js); self.assertIn('drone.setPopupContent(dronePopup(telemetry))',map_js)
  self.assertIn('uniquePoints.size>=2',map_js)
  app_js=(ROOT/'frontend'/'js'/'app.js').read_text(encoding='utf-8')
  self.assertIn('MAX ALTITUDE EXCEEDED',app_js); self.assertIn('ALTITUDE APPROACHING LIMIT',app_js); self.assertIn("telemetry_status:lastConnectionStatus.connected?'STALE'",app_js)
 def test_clean_start_safe_telemetry(self):
  t=self.client.get('/api/drone/telemetry',headers=self.h).json()
  self.assertEqual((t['latitude'],t['longitude']),(None,None)); self.assertEqual(t['altitude'],0.0); self.assertEqual(t['ground_speed'],0.0); self.assertEqual(t['battery'],{'percentage':100.0,'voltage':16.8,'current':0.0}); self.assertEqual(t['flight_mode'],'STABILIZE'); self.assertFalse(t['armed']); self.assertEqual(t['gps_satellites'],0); self.assertIsNone(t['gps_accuracy']); self.client.post('/api/drone/connect',headers=self.h); connected=self.client.get('/api/drone/telemetry',headers=self.h).json(); self.assertIsNone(connected['latitude']); self.assertEqual(connected['gps_satellites'],0)
 def test_import_json_updates_backend_and_does_not_execute_controls(self):
  r=self.client.post('/api/telemetry/import',headers=self.h,json=self.demo()); self.assertEqual(r.status_code,200,r.text)
  t=r.json()['telemetry']; self.assertEqual(t['source'],'simulation'); self.assertEqual(t['altitude'],120.5); self.assertEqual(t['ground_speed'],8.4); self.assertEqual(t['battery'],{'percentage':82.0,'voltage':15.9,'current':4.2}); self.assertEqual(t['flight_mode'],'LOITER'); self.assertTrue(t['armed']); self.assertEqual((t['latitude'],t['longitude']),(13.0827,80.2707)); self.assertEqual(t['gps_satellites'],14); self.assertEqual(t['gps_accuracy'],2.5)
  self.assertIsNone(backend.simulator.flight); self.assertEqual(backend.simulator.index,0)
  self.assertEqual(self.client.get('/api/drone/telemetry',headers=self.h).json()['latitude'],13.0827)
 def test_requested_sample_and_nested_gps_import(self):
  sample={'source':'simulation','timestamp':None,'latitude':16.5427,'longitude':79.5890,'altitude':20.0,'ground_speed':5.0,'heading':90.0,'battery':{'percentage':85,'voltage':15.8,'current':3.2},'flight_mode':'LOITER','armed':True,'gps_satellites':12,'gps_accuracy':5.0}
  r=self.client.post('/api/telemetry/import',headers=self.h,json=sample); self.assertEqual(r.status_code,200,r.text)
  t=self.client.get('/api/drone/telemetry',headers=self.h).json()
  self.assertEqual((t['latitude'],t['longitude'],t['altitude'],t['ground_speed'],t['heading']),(16.5427,79.5890,20.0,5.0,90.0))
  self.assertEqual(t['battery'],{'percentage':85.0,'voltage':15.8,'current':3.2}); self.assertEqual(t['flight_mode'],'LOITER'); self.assertTrue(t['armed']); self.assertEqual(t['gps_satellites'],12)
  self.client.post('/api/telemetry/reset',headers=self.h)
  nested={'source':'simulation','gps':{'latitude':16.5427,'longitude':79.5890,'satellites':12,'accuracy':5.0},'altitude':20,'ground_speed':5}
  r=self.client.post('/api/telemetry/import',headers=self.h,json=nested); self.assertEqual(r.status_code,200,r.text)
  t=r.json()['telemetry']; self.assertEqual((t['latitude'],t['longitude'],t['gps_satellites'],t['gps_accuracy']),(16.5427,79.5890,12,5.0))
 def test_import_requires_a_usable_gps_fix(self):
  d={'source':'simulation','altitude':20,'ground_speed':5}
  r=self.client.post('/api/telemetry/import',headers=self.h,json=d)
  self.assertEqual(r.status_code,400); self.assertEqual(r.json()['detail'],'Invalid telemetry data: latitude/longitude are required.')
 def test_invalid_battery_and_gps_rejected(self):
  d=self.demo(); d['battery']['percentage']=101; r=self.client.post('/api/telemetry/import',headers=self.h,json=d); self.assertEqual(r.status_code,400); self.assertIn('Battery percentage',r.json()['detail'])
  d=self.demo(); d['latitude']=91; r=self.client.post('/api/telemetry/import',headers=self.h,json=d); self.assertEqual(r.status_code,400); self.assertIn('GPS',r.json()['detail'])
  d=self.demo(); d['ground_speed']='fast'; r=self.client.post('/api/telemetry/import',headers=self.h,json=d); self.assertEqual(r.status_code,400)
  raw='{"source":"simulation","altitude":NaN,"battery":{"percentage":80}}'; r=self.client.post('/api/telemetry/import',headers={**self.h,'Content-Type':'application/json'},content=raw); self.assertEqual(r.status_code,400)
 def test_reset_clears_imported_state_and_track(self):
  self.client.post('/api/telemetry/import',headers=self.h,json=self.demo()); r=self.client.post('/api/telemetry/reset',headers=self.h); self.assertEqual(r.status_code,200)
  t=self.client.get('/api/drone/telemetry',headers=self.h).json(); self.assertEqual((t['latitude'],t['longitude']),(None,None)); self.assertEqual(t['altitude'],0.0); self.assertEqual(t['ground_speed'],0.0); self.assertEqual(t['battery']['percentage'],100.0); self.assertEqual(t['battery']['voltage'],16.8); self.assertEqual(t['battery']['current'],0.0); self.assertEqual(t['flight_mode'],'STABILIZE'); self.assertFalse(t['armed']); self.assertEqual(t['gps_satellites'],0); self.assertEqual(t['track'],[])
 def test_phone_is_not_a_drone_source(self):
  r=self.client.post('/api/config/source',headers=self.h,json={'mode':'phone'}); self.assertEqual(r.status_code,400)
  self.assertEqual(self.client.get('/api/drone/telemetry',headers=self.h).json()['source'],'simulation')
 def test_websocket_broadcasts_current_imported_state(self):
  self.client.post('/api/telemetry/import',headers=self.h,json=self.demo())
  with self.client.websocket_connect('/ws/telemetry') as ws:
   d=ws.receive_json(); self.assertEqual(d['telemetry']['altitude'],120.5); self.assertEqual(d['telemetry']['battery']['percentage'],82); self.assertEqual(d['telemetry']['latitude'],13.0827)
 def test_import_pushes_state_to_existing_websocket_broadcaster(self):
  sample=self.demo()
  with patch('backend.api.telemetry.telemetry_broadcaster.broadcast',new_callable=AsyncMock) as broadcast:
   r=self.client.post('/api/telemetry/import',headers=self.h,json=sample)
   self.assertEqual(r.status_code,200,r.text); broadcast.assert_awaited_once()
   packet=broadcast.await_args.args[0]
   self.assertEqual(packet['telemetry']['latitude'],sample['latitude']); self.assertEqual(packet['telemetry']['heading'],sample['heading']); self.assertEqual(packet['track'],[[sample['latitude'],sample['longitude']]])
 def test_mission_simulation_still_completes_and_logs(self):
  before=len(self.client.get('/api/flights',headers=self.h).json())
  self.client.post('/api/drone/connect',headers=self.h)
  h=backend.loadj('drone.json')['home_position']; items=[{'latitude':h['latitude']+0.00002,'longitude':h['longitude'],'altitude':0,'speed':10,'command':'WAYPOINT'}]
  m=self.client.post('/api/missions',headers=self.h,json={'name':'regression mission','items':items}).json(); self.assertTrue(self.client.post(f"/api/missions/{m['id']}/validate",headers=self.h).json()['valid']); self.assertEqual(self.client.post(f"/api/missions/{m['id']}/upload",headers=self.h).json()['uploaded'],1); self.assertEqual(self.client.post('/api/drone/start_mission',headers=self.h).status_code,200)
  for _ in range(8): backend.simulator.last=time.monotonic()-2; self.client.get('/api/drone/telemetry',headers=self.h)
  logs=self.client.get('/api/flights',headers=self.h).json(); self.assertGreater(len(logs),before); self.assertEqual(logs[0]['status'],'COMPLETED')
 def test_current_location_is_frontend_only(self):
  t=self.client.get('/api/drone/telemetry',headers=self.h).json(); map_source=(ROOT/'frontend'/'js'/'map.js').read_text(encoding='utf-8')
  self.assertIn('navigator.geolocation.getCurrentPosition',map_source); self.assertNotIn('/api/telemetry/import',map_source); self.assertEqual(self.client.get('/api/drone/telemetry',headers=self.h).json(),t)
 def test_database_parent_created_on_first_use(self):
  old=backend.DB
  try:
   with tempfile.TemporaryDirectory() as tmp:
    backend.DB=Path(tmp)/'new'/'backend'/'database'/'test.sqlite'; backend.init_db(); self.assertTrue(backend.DB.exists())
  finally: backend.DB=old
 def test_dashboard_wires_import_reset_and_separate_location(self):
  page=self.client.get('/').text; self.assertIn('id="importTelemetryBtn"',page); self.assertIn('id="resetSimulationBtn"',page); self.assertIn('id="currentLocationBtn"',page); self.assertNotIn('data-mode="phone"',page); self.assertIn('/static/js/map.js',page); self.assertIn('/static/js/telemetry-import.js',page)
 def test_real_adapter_remains_fail_closed(self):
  r=self.client.post('/api/config/source',headers=self.h,json={'mode':'mavlink'}); self.assertFalse(r.json()['adapter_ready']); self.assertEqual(self.client.post('/api/drone/connect',headers=self.h).status_code,501); self.assertEqual(self.client.post('/api/telemetry/import',headers=self.h,json=self.demo()).status_code,409)
  t=self.client.get('/api/drone/telemetry',headers=self.h).json(); self.assertEqual(t['source'],'mavlink'); self.assertIsNone(t['latitude']); self.assertIsNone(t['battery']['percentage'])
 def test_source_and_limits(self):
  self.assertEqual(self.client.get('/api/config',headers=self.h).status_code,200); self.assertEqual(self.client.post('/api/config/source',headers=self.h,json={'mode':'simulation'}).status_code,200)
  m=self.client.post('/api/missions',headers=self.h,json={'name':'limit','items':[{'latitude':13.083,'longitude':80.2707,'altitude':999,'speed':2,'command':'WAYPOINT'}]}).json(); v=self.client.post(f"/api/missions/{m['id']}/validate",headers=self.h).json(); self.assertFalse(v['valid']); self.assertTrue(any('50 m' in e for e in v['errors']))
if __name__=='__main__': unittest.main()
