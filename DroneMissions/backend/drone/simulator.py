"""JSON-driven simulation adapter implementing the common drone interface."""
import json, math, time, uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from backend.drone.interface import DroneInterface

class SimulationDrone(DroneInterface):
 def __init__(self, load_json, save_json, database):
  self.loadj=load_json; self.savej=save_json; self.db=database
  self.connected=False; self.armed=False; self.paused=False; self.items=[]; self.index=0; self.last=time.monotonic(); self.track=[]; self.flight=None; self._state={}
  self.reset()
 def reset(self):
  self.armed=False; self.paused=False; self.items=[]; self.index=0; self.track=[]; self.flight=None; self.imported=False
  self.last_telemetry_at=None
  self._state={'latitude':None,'longitude':None,'altitude':0.0,'ground_speed':0.0,'air_speed':0.0,'heading':0.0,'battery':100.0,'voltage':16.8,'current':0.0,'gps_satellites':0,'gps_accuracy':None,'flight_mode':'STABILIZE','armed':False,'roll':0.0,'pitch':0.0,'yaw':0.0,'source':'simulation','timestamp':None}; self.last=time.monotonic()
  return self.normalized()
 def reset_simulation(self): return self.reset()
 @property
 def telemetry(self): return self.normalized()
 @property
 def current_telemetry(self): return self.normalized()
 def normalized(self):
  t=self._state
  return {'source':'simulation','timestamp':t.get('timestamp'),'latitude':t.get('latitude'),'longitude':t.get('longitude'),'altitude':t.get('altitude'),'ground_speed':t.get('ground_speed'),'heading':t.get('heading'),'battery':{'percentage':t.get('battery'),'voltage':t.get('voltage'),'current':t.get('current')},'flight_mode':t.get('flight_mode'),'armed':bool(t.get('armed',False)),'gps_satellites':t.get('gps_satellites'),'gps_accuracy':t.get('gps_accuracy'),'roll':t.get('roll',0.0),'pitch':t.get('pitch',0.0),'yaw':t.get('yaw',t.get('heading') or 0.0)}
 def import_telemetry(self,data):
  t=data.model_dump(mode='json'); gps=t.get('gps') or {}; battery=t.get('battery') or {}
  self._state={'latitude':t.get('latitude') if t.get('latitude') is not None else gps.get('latitude'),'longitude':t.get('longitude') if t.get('longitude') is not None else gps.get('longitude'),'altitude':t.get('altitude'),'ground_speed':t.get('ground_speed'),'air_speed':t.get('ground_speed'),'heading':t.get('heading'),'battery':battery.get('percentage'),'voltage':battery.get('voltage'),'current':battery.get('current'),'gps_satellites':t.get('gps_satellites') if t.get('gps_satellites') is not None else gps.get('satellites'),'gps_accuracy':t.get('gps_accuracy') if t.get('gps_accuracy') is not None else gps.get('accuracy'),'flight_mode':t.get('flight_mode'),'armed':bool(t.get('armed',False)),'roll':0.0,'pitch':0.0,'yaw':t.get('heading') or 0.0,'source':'simulation','timestamp':t.get('timestamp')}
  self.armed=bool(t.get('armed',False)); self.paused=False; self.imported=True; self.flight=None; self.index=0
  lat,lon=self._state['latitude'],self._state['longitude']; self.track=[[lat,lon]] if lat is not None and lon is not None else []
  return self.normalized()
 async def connect(self):
  self.connected=True
  return await self.get_status()
 async def disconnect(self): self.connected=False; self.armed=False; self._state['armed']=False; return await self.get_status()
 async def get_status(self):
  d=self.loadj('drone.json'); interval=max(.2,float(self.loadj('simulation.json').get('telemetry_interval',1))); age=(time.monotonic()-self.last_telemetry_at) if self.last_telemetry_at is not None else None
  telemetry_status='NOT RECEIVING' if not self.connected or age is None else ('STALE' if age>max(3*interval,5) else 'RECEIVING')
  heartbeat='OK' if telemetry_status=='RECEIVING' else ('STALE' if telemetry_status=='STALE' else '--')
  state='CONNECTED' if self.connected else 'DISCONNECTED'
  return {'connected':self.connected,'state':state,'connection_state':state,'source':'simulation','mode':'SIMULATION','connection_type':'SIMULATION','connection_method':'Simulation' if self.connected else None,'link_status':'GOOD' if self.connected else 'OFFLINE','link_quality':'GOOD' if self.connected else 'OFFLINE','link_quality_percent':None,'telemetry_status':telemetry_status,'heartbeat':heartbeat,'heartbeat_at':datetime.fromtimestamp(self.last_telemetry_at,timezone.utc).isoformat() if self.last_telemetry_at is not None and self.connected else None,'heartbeat_source':'SIMULATED' if heartbeat=='OK' else None,'protocol':'SIMULATION' if self.connected else None,'drone':d['drone_name'],'armed':self.armed,'flight_mode':self._state['flight_mode'],'adapter_ready':True,'simulated':True,'message':'JSON simulator active; connection health is simulated.' if self.connected else 'Disconnected'}
 async def get_telemetry(self):
  if self.connected: await self.tick(); self.last_telemetry_at=time.monotonic()
  return self.normalized()
 async def command(self,name,payload=None):
  name=name.lower(); p=self.loadj('parameters.json'); t=self._state
  if name=='connect': return await self.connect()
  if name=='disconnect': return await self.disconnect()
  if not self.connected: raise HTTPException(409,'Connect to the selected data source first')
  self.imported=False
  if name in ('takeoff','start_mission','rtl') and (t.get('latitude') is None or t.get('longitude') is None):
   h=self.loadj('drone.json')['home_position']; t.update({'latitude':h['latitude'],'longitude':h['longitude'],'gps_satellites':12,'gps_accuracy':self.loadj('simulation.json').get('gps_accuracy',3)})
  if name=='arm': self.armed=True; t['armed']=True; t['flight_mode']='GUIDED'; self.flight={'start':time.time(),'battery':t['battery'],'max_alt':t['altitude'],'distance':0,'max_speed':0}
  elif name=='disarm': self.armed=False; t['armed']=False; t['ground_speed']=0; t['flight_mode']='STANDBY'
  elif name=='takeoff':
   if not self.armed: raise HTTPException(409,'Arm the simulator before takeoff')
   t['flight_mode']='TAKEOFF'; t['target_altitude']=float((payload or {}).get('altitude',p['flight']['default_altitude']) if (payload or {}).get('altitude') is not None else p['flight']['default_altitude'])
  elif name=='land': t['flight_mode']='LAND'; t['target_altitude']=0
  elif name=='rtl':
   home=self.loadj('drone.json')['home_position']; t['flight_mode']='AUTO'; self.items=[{'latitude':home['latitude'],'longitude':home['longitude'],'altitude':p['flight']['rtl_altitude'],'speed':p['flight']['default_speed'],'command':'WAYPOINT'},{'latitude':home['latitude'],'longitude':home['longitude'],'altitude':0,'speed':p['flight']['default_speed'],'command':'LAND'}]; self.index=0
  elif name=='pause': self.paused=True; t['flight_mode']='PAUSED'
  elif name=='resume': self.paused=False; t['flight_mode']='AUTO' if self.items else 'GUIDED'
  elif name=='start_mission':
   if not self.items: raise HTTPException(409,'Upload a mission before starting')
   if not self.armed: self.armed=True; t['armed']=True
   self.index=0; self.paused=False; t['flight_mode']='AUTO'; t['target_altitude']=self.items[0].get('altitude',p['flight']['default_altitude'])
   self.flight={'start':time.time(),'battery':t['battery'],'max_alt':t['altitude'],'distance':0,'max_speed':0}
  else: raise HTTPException(404,'Unsupported command')
  t['timestamp']=datetime.now(timezone.utc).isoformat()
  return {'ok':True,'telemetry':self.normalized(),'status':await self.get_status()}
 async def upload_mission(self,items):
  if not self.connected: raise HTTPException(409,'Connect first')
  self.items=items; self.index=0; return {'ok':True,'uploaded':len(items),'mission_items':self.items}
 async def download_mission(self): return self.items
 async def get_parameters(self): return self.loadj('parameters.json')
 async def set_parameter(self,name,value):
  p=self.loadj('parameters.json'); parts=name.split('.'); cur=p
  for key in parts[:-1]:
   if key not in cur: raise HTTPException(404,'Parameter not found')
   cur=cur[key]
  if parts[-1] not in cur: raise HTTPException(404,'Parameter not found')
  cur[parts[-1]]=value; self.savej('parameters.json',p); return {'name':name,'value':value,'source':'JSON CONFIG'}
 async def tick(self):
  t=self._state; s=self.loadj('simulation.json'); p=self.loadj('parameters.json'); now=time.monotonic(); dt=min(now-self.last,3); self.last=now
  t.pop('target_altitude',None) if False else None
  if self.imported:
   if self.connected:
    with self.db() as c: c.execute('insert into telemetry(ts,payload) values(?,?)',(t.get('timestamp') or datetime.now(timezone.utc).isoformat(),json.dumps(self.normalized())))
    self.check_alerts()
   return
  if self.armed and not self.paused:
   if t['flight_mode'] in ('TAKEOFF','LAND','RTL'):
    target=t.get('target_altitude',0); delta=target-t['altitude']; step=max(.2,float(s['movement_speed'])*dt*.5); t['altitude']+=max(-step,min(step,delta)); t['ground_speed']=max(0.5,float(s['movement_speed']) if abs(delta)>.5 else 0)
    if abs(delta)<.5:
     if t['flight_mode']=='TAKEOFF': t['flight_mode']='GUIDED'
     elif t['flight_mode']=='LAND': t['flight_mode']='STANDBY'; self.armed=False; t['armed']=False; t['ground_speed']=0; self.finish_flight('COMPLETED')
   if self.items and t['flight_mode']=='AUTO':
    if self.index>=len(self.items): t['flight_mode']='HOLD'; t['ground_speed']=0; self.armed=False; t['armed']=False; self.finish_flight('COMPLETED')
    else:
     wp=self.items[self.index]; lat,lon=t['latitude'],t['longitude']; dlat=(wp['latitude']-lat)*111320; dlon=(wp['longitude']-lon)*111320*math.cos(math.radians(lat)); dist=math.hypot(dlat,dlon); speed=min(float(wp.get('speed',p['flight']['default_speed'])),float(p['flight']['max_speed']),float(s['movement_speed'])); t['ground_speed']=speed; t['air_speed']=speed*1.08; t['heading']=(math.degrees(math.atan2(dlon,dlat))+360)%360; t['yaw']=t['heading']; move=min(dist,speed*dt)
     if dist>0.1:
      t['latitude']+=dlat/dist*move/111320; t['longitude']+=dlon/dist*move/(111320*max(.1,math.cos(math.radians(lat))))
     if self.flight: self.flight['distance']+=move; self.flight['max_alt']=max(self.flight['max_alt'],t['altitude']); self.flight['max_speed']=max(self.flight.get('max_speed',0),speed)
     target=float(wp.get('altitude',p['flight']['default_altitude'])); t['altitude']+=max(-speed*dt*.4,min(speed*dt*.4,target-t['altitude']))
     if dist<2 and abs(target-t['altitude'])<1: self.index+=1
   drain=float(s['battery_drain_rate'])*dt*(1 if self.armed else .08); t['battery']=max(0,t['battery']-drain); t['voltage']=round(13.2+3.6*t['battery']/100,2); t['current']=round((2+t['ground_speed']*.7) if self.armed else 0,1)
   t['roll']=round(math.sin(now*0.7)*2,1); t['pitch']=round(math.cos(now*.5)*1.5,1); t['gps_satellites']=max(0,14-int(abs(math.sin(now/40))*2)); t['timestamp']=datetime.now(timezone.utc).isoformat()
  if self.connected:
   if t.get('latitude') is not None and t.get('longitude') is not None: self.track.append([t['latitude'],t['longitude']]); self.track=self.track[-300:]
   with self.db() as c: c.execute('insert into telemetry(ts,payload) values(?,?)',(t.get('timestamp') or datetime.now(timezone.utc).isoformat(),json.dumps(self.normalized())))
   self.check_alerts()
 def check_alerts(self):
  t=self._state; p=self.loadj('parameters.json'); alerts=[]
  if t.get('battery') is not None and t['battery']<=p['battery']['critical_battery']: alerts.append(('CRITICAL','CRITICAL BATTERY'))
  elif t.get('battery') is not None and t['battery']<=p['battery']['low_battery_warning']: alerts.append(('WARNING','LOW BATTERY'))
  if t.get('gps_satellites') is not None and t['gps_satellites']<p['gps']['minimum_satellites']: alerts.append(('WARNING','LOW GPS SATELLITES'))
  if t.get('altitude') is not None and t['altitude']>p['flight']['max_altitude']: alerts.append(('WARNING','HIGH ALTITUDE'))
  for sev,msg in alerts:
   with self.db() as c:
    if not c.execute('select id from alerts where message=? and acknowledged=0 order by id desc limit 1',(msg,)).fetchone(): c.execute('insert into alerts(ts,severity,message) values(?,?,?)',(datetime.now(timezone.utc).isoformat(),sev,msg))
 def finish_flight(self,status):
  if not self.flight:return
  f=self.flight; ident=str(uuid.uuid4())[:8]
  with self.db() as c: c.execute('insert into flights values(?,?,?,?,?,?,?,?,?,?)',(ident,self.loadj('drone.json')['drone_name'],datetime.fromtimestamp(f['start'],timezone.utc).isoformat(),datetime.now(timezone.utc).isoformat(),time.time()-f['start'],f['distance'],max(f['max_alt'],self._state['altitude']),self._state['ground_speed'],f['battery']-self._state['battery'],status))
  self.flight=None

