import asyncio, json, math, os, sqlite3, time, uuid, hmac, hashlib, base64
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from backend.drone.interface import DroneInterface
from backend.api.telemetry import build_telemetry_router
from backend.api.websocket import build_websocket_router
from backend.api.map import build_map_router
from backend.api.parameters import build_parameters_router
from backend.api.gimbal import build_gimbal_router

ROOT=Path(__file__).resolve().parent.parent
CFG=ROOT/'config'; DB=ROOT/'backend'/'database'/'drone_missions.db'
def loadj(name): return json.loads((CFG/name).read_text(encoding='utf-8-sig'))
def savej(name,obj): (CFG/name).write_text(json.dumps(obj,indent=2),encoding='utf-8')

@contextmanager
def db():
 DB.parent.mkdir(parents=True, exist_ok=True)
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
 try:
  yield c
  c.commit()
 except Exception:
  c.rollback()
  raise
 finally:
  c.close()
def init_db():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role TEXT DEFAULT 'operator'); CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY,name TEXT,items TEXT,created_at TEXT,updated_at TEXT); CREATE TABLE IF NOT EXISTS flights(id TEXT PRIMARY KEY,drone TEXT,started TEXT,ended TEXT,duration REAL,distance REAL,max_altitude REAL,max_speed REAL,battery_used REAL,status TEXT); CREATE TABLE IF NOT EXISTS telemetry(id INTEGER PRIMARY KEY,ts TEXT,payload TEXT); CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY,ts TEXT,severity TEXT,message TEXT,acknowledged INTEGER DEFAULT 0); CREATE TABLE IF NOT EXISTS parameters(name TEXT PRIMARY KEY,value TEXT,source TEXT); CREATE TABLE IF NOT EXISTS drones(id TEXT PRIMARY KEY,name TEXT,mode TEXT);''')
  user_columns={r['name'] for r in c.execute('PRAGMA table_info(users)').fetchall()}
  if 'full_name' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN full_name TEXT')
  if 'email' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN email TEXT')
  c.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique ON users(email) WHERE email IS NOT NULL AND email != ''")
  if not c.execute('select 1 from users where username=?',('admin',)).fetchone(): c.execute('insert into users(username,password_hash) values(?,?)',('admin',pw_hash('admin123')))
  d=loadj('drone.json'); c.execute('insert or ignore into drones values(?,?,?)',(d['drone_id'],d['drone_name'],d['mode']))
def fetchall(sql,args=()):
 with db() as c: return c.execute(sql,args).fetchall()
def fetchone(sql,args=()):
 with db() as c: return c.execute(sql,args).fetchone()
def pw_hash(p): return hashlib.pbkdf2_hmac('sha256',p.encode(),b'drone-missions-demo',160000).hex()
SECRET=os.getenv('JWT_SECRET','development-secret-change-before-deployment').encode()
def token(user):
 now=int(time.time()); head={'alg':'HS256','typ':'JWT'}; body={'sub':user,'iat':now,'exp':now+43200}
 enc=lambda x:base64.urlsafe_b64encode(json.dumps(x,separators=(',',':')).encode()).decode().rstrip('=')
 a,b=enc(head),enc(body); sig=base64.urlsafe_b64encode(hmac.new(SECRET,f'{a}.{b}'.encode(),hashlib.sha256).digest()).decode().rstrip('='); return f'{a}.{b}.{sig}'
def current_user(auth):
 if not auth or not auth.startswith('Bearer '): raise HTTPException(401,'Authentication required')
 try:
  a,b,s=auth[7:].split('.'); expected=base64.urlsafe_b64encode(hmac.new(SECRET,f'{a}.{b}'.encode(),hashlib.sha256).digest()).decode().rstrip('=')
  payload=json.loads(base64.urlsafe_b64decode(b+'==='))
  if not hmac.compare_digest(s,expected) or payload['exp']<time.time(): raise ValueError()
  return payload['sub']
 except Exception: raise HTTPException(401,'Invalid or expired token')

from backend.drone.simulator import SimulationDrone
from backend.drone.gimbal_simulator import GimbalSimulator

class PhoneTelemetry(DroneInterface):
 def __init__(self): self.connected=False; self.data={}; self.items=[]
 async def connect(self): self.connected=True; return await self.get_status()
 async def disconnect(self): self.connected=False; return await self.get_status()
 async def get_status(self): return {'connected':self.connected,'mode':'PHONE','connection_type':'PHONE','drone':'Phone sensor demonstration','armed':False,'flight_mode':'PHONE TELEMETRY','adapter_ready':True,'message':'Phone browser sensor demo; not a flight controller.'}
 async def get_telemetry(self):
  d=self.data; return {'source':'phone','timestamp':datetime.now(timezone.utc).isoformat(),'latitude':d.get('latitude'),'longitude':d.get('longitude'),'altitude':d.get('altitude'),'ground_speed':d.get('ground_speed'),'air_speed':d.get('air_speed',d.get('ground_speed')),'heading':d.get('heading'),'battery':{'percentage':d.get('battery'),'voltage':d.get('voltage'),'current':d.get('current')},'flight_mode':'PHONE TELEMETRY','armed':False,'gps_satellites':d.get('gps_satellites'),'gps_accuracy':None,'roll':d.get('roll'),'pitch':d.get('pitch'),'yaw':d.get('yaw',d.get('heading'))}
 async def command(self,name,payload=None): raise HTTPException(409,'Flight commands are disabled in Phone Telemetry mode')
 async def upload_mission(self,items): raise HTTPException(409,'Mission upload is unavailable in Phone Telemetry mode')
 async def download_mission(self): return []
 async def get_parameters(self): return loadj('parameters.json')
 async def set_parameter(self,name,value): return {'name':name,'value':value,'source':'JSON CONFIG'}
 async def ingest(self,data):
  allowed={'latitude','longitude','ground_speed','heading','roll','pitch','yaw','altitude','battery','voltage','current','gps_satellites'}; self.data={k:v for k,v in data.items() if k in allowed}; self.data.update({'air_speed':self.data.get('ground_speed',0),'armed':False,'flight_mode':'PHONE TELEMETRY'})

class MAVLinkDrone(DroneInterface):
 async def connect(self): raise HTTPException(501,'Real drone connection is not configured.')
 async def disconnect(self): return {'connected':False}
 async def get_status(self): return {'connected':False,'state':'DISCONNECTED','mode':'REAL DRONE','source':'real_drone','connection_type':'OTHER','connection_state':'DISCONNECTED','connection_method':'NOT CONFIGURED','link_status':'OFFLINE','link_quality':'OFFLINE','link_quality_percent':None,'telemetry_status':'NOT RECEIVING','heartbeat':'--','heartbeat_at':None,'heartbeat_source':None,'protocol':'NOT CONFIGURED','simulated':False,'adapter_ready':False,'message':'REAL DRONE · NOT CONFIGURED. Confirm company hardware details and validate an adapter before connecting.'}
 async def get_telemetry(self): return {'source':'mavlink','timestamp':None,'latitude':None,'longitude':None,'altitude':None,'ground_speed':None,'air_speed':None,'heading':None,'battery':{'percentage':None,'voltage':None,'current':None},'flight_mode':None,'armed':False,'gps_satellites':None,'gps_accuracy':None,'roll':None,'pitch':None,'yaw':None}
 async def command(self,name,payload=None): raise HTTPException(501,'Physical commands disabled: adapter and company safety validation required')
 async def upload_mission(self,items): raise HTTPException(501,'Physical mission upload disabled until adapter validation')
 async def download_mission(self): raise HTTPException(501,'Physical mission download disabled until adapter validation')
 async def get_parameters(self): raise HTTPException(501,'Physical parameters unavailable until adapter validation')
 async def set_parameter(self,name,value): raise HTTPException(501,'Physical parameter writes disabled until adapter validation')

init_db(); simulator=SimulationDrone(loadj,savej,db); phone=PhoneTelemetry(); gimbal=GimbalSimulator(loadj); app=FastAPI(title='Drone Missions | Ground Control Station',version='1.0.0'); app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])
def source():
 mode=os.getenv('DATA_SOURCE',loadj('drone.json').get('mode','SIMULATION')).lower()
 return {'simulation':simulator,'mavlink':MAVLinkDrone()}.get(mode,simulator)
class Login(BaseModel): username:str; password:str
class Register(BaseModel): username:str; password:str; full_name:str|None=None; email:str|None=None
class MissionIn(BaseModel): name:str='New Mission'; items:list[dict[str,Any]]=[]
class PhoneIn(BaseModel): data:dict[str,Any]
def authdep(authorization:str|None=Header(default=None)): return current_user(authorization)
app.include_router(build_telemetry_router(simulator,source,authdep,gimbal))
app.include_router(build_gimbal_router(gimbal,authdep))
app.include_router(build_websocket_router(source,simulator,loadj))
app.include_router(build_map_router(authdep))
app.include_router(build_parameters_router(ROOT,loadj,savej,source,simulator,authdep))
@app.get('/api/health')
async def health(): return {'ok':True,'app':'Drone Missions','time':datetime.now(timezone.utc).isoformat()}
@app.post('/api/auth/login')
async def login(body:Login):
 with db() as c: row=c.execute('select * from users where username=? or lower(email)=lower(?)',(body.username,body.username)).fetchone()
 if not row or not hmac.compare_digest(row['password_hash'],pw_hash(body.password)): raise HTTPException(401,'Incorrect username or password')
 return {'access_token':token(row['username']),'token_type':'bearer','user':{'username':row['username'],'full_name':row['full_name'],'email':row['email'],'role':row['role']}}
@app.post('/api/auth/register')
async def register(body:Register):
 username=body.username.strip(); full_name=(body.full_name or '').strip(); email=(body.email or '').strip().lower()
 if not username or len(username)>80: raise HTTPException(400,'Username must contain 1 to 80 characters')
 if len(body.password)<8: raise HTTPException(400,'Password must contain at least 8 characters')
 if bool(full_name)!=bool(email): raise HTTPException(400,'Full name and email must be provided together')
 if full_name and (len(full_name)>120 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",email)): raise HTTPException(400,'Enter a valid full name and email address')
 try:
  with db() as c:c.execute('insert into users(username,password_hash,full_name,email) values(?,?,?,?)',(username,pw_hash(body.password),full_name or None,email or None))
 except sqlite3.IntegrityError as exc: raise HTTPException(409,'Email is already registered' if 'email' in str(exc).lower() else 'Username is already registered')
 return {'access_token':token(username),'token_type':'bearer','user':{'username':username,'full_name':full_name or None,'email':email or None}}
@app.get('/api/auth/me')
async def me(user=__import__('fastapi').Depends(authdep)): return {'username':user}
@app.get('/api/drones')
async def drones(user=__import__('fastapi').Depends(authdep)): return [dict(x) for x in fetchall('select * from drones')]
@app.post('/api/drones')
async def create_drone(body:dict,user=__import__('fastapi').Depends(authdep)):
 with db() as c:c.execute('insert into drones values(?,?,?)',(body.get('id',str(uuid.uuid4())[:8]),body['name'],body.get('mode','SIMULATION')))
 return {'ok':True}
@app.get('/api/drone/status')
async def status(user=__import__('fastapi').Depends(authdep)): return await source().get_status()
@app.post('/api/drone/auto-connect')
async def auto_connect(user=__import__('fastapi').Depends(authdep)):
 # Simulation is the only implemented and verified auto-connect candidate today.
 # The real-drone placeholder is deliberately skipped until its adapter is validated.
 os.environ['DATA_SOURCE']='simulation'
 await simulator.connect()
 telemetry=await simulator.get_telemetry()
 state=await simulator.get_status()
 if not state.get('connected') or telemetry.get('source')!='simulation' or state.get('telemetry_status')!='RECEIVING' or state.get('heartbeat')!='OK':
  raise HTTPException(503,'Simulation connection could not verify telemetry and heartbeat')
 return {'connected':True,'attempted':['SIMULATION'],'status':state,'telemetry':telemetry,'message':'Connected to JSON simulation; telemetry and simulated heartbeat verified.'}
@app.post('/api/drone/{action}')
async def control(action:str,body:dict|None=None,user=__import__('fastapi').Depends(authdep)):
 if action not in {'connect','disconnect','arm','disarm','takeoff','land','rtl','pause','resume','start_mission','emergency_stop'}: raise HTTPException(404,'Unknown control')
 if action=='emergency_stop': action='land'
 return await source().command(action,body)
@app.get('/api/drone/telemetry')
async def telemetry(user=__import__('fastapi').Depends(authdep)):
 t=await source().get_telemetry(); return {**t,'track':getattr(simulator,'track',[]),'mission_index':simulator.index if source() is simulator else 0}
@app.post('/api/phone/telemetry')
async def phone_ingest(body:PhoneIn): await phone.ingest(body.data); return {'ok':True,'mode':'PHONE TELEMETRY (ISOLATED)','received':phone.data}
@app.get('/api/missions')
async def missions(user=__import__('fastapi').Depends(authdep)):
 return [{'id':r['id'],'name':r['name'],'items':json.loads(r['items']),'created_at':r['created_at'],'updated_at':r['updated_at']} for r in fetchall('select * from missions order by updated_at desc')]
@app.post('/api/missions')
async def create_mission(body:MissionIn,user=__import__('fastapi').Depends(authdep)):
 ident=str(uuid.uuid4())[:8]; now=datetime.now(timezone.utc).isoformat()
 with db() as c:c.execute('insert into missions values(?,?,?, ?,?)',(ident,body.name,json.dumps(body.items),now,now))
 return {'id':ident,'name':body.name,'items':body.items}
@app.get('/api/missions/{ident}')
async def get_mission(ident:str,user=__import__('fastapi').Depends(authdep)):
 r=fetchone('select * from missions where id=?',(ident,))
 if not r: raise HTTPException(404,'Mission not found')
 return {'id':r['id'],'name':r['name'],'items':json.loads(r['items'])}
@app.put('/api/missions/{ident}')
async def update_mission(ident:str,body:MissionIn,user=__import__('fastapi').Depends(authdep)):
 with db() as c:cur=c.execute('update missions set name=?,items=?,updated_at=? where id=?',(body.name,json.dumps(body.items),datetime.now(timezone.utc).isoformat(),ident))
 if cur.rowcount==0: raise HTTPException(404,'Mission not found')
 return {'ok':True,'id':ident}
@app.delete('/api/missions/{ident}')
async def delete_mission(ident:str,user=__import__('fastapi').Depends(authdep)):
 with db() as c:c.execute('delete from missions where id=?',(ident,))
 return {'ok':True}
def validate(items):
 p=loadj('parameters.json'); errs=[]; warnings=[]; valid={'WAYPOINT','TAKEOFF','LAND','RTL','LOITER','DELAY'}
 if not items: errs.append('Mission contains no waypoints.')
 h=loadj('drone.json')['home_position']; radius=p['geofence']['radius']
 for i,w in enumerate(items,1):
  for k in ('latitude','longitude','altitude','speed','command'):
   if w.get(k) is None: errs.append(f'Waypoint {i}: missing {k}.')
  try:
   lat=float(w['latitude']); lon=float(w['longitude']); alt=float(w['altitude']); speed=float(w.get('speed',p['flight']['default_speed']))
   label=f'WP{i}'
   if not math.isfinite(lat) or not -90<=lat<=90: errs.append(f'{label} latitude must be between -90 and +90 degrees.')
   if not math.isfinite(lon) or not -180<=lon<=180: errs.append(f'{label} longitude must be between -180 and +180 degrees.')
   if not math.isfinite(alt) or alt<0: errs.append(f'{label} altitude must be a finite non-negative number.')
   if math.isfinite(alt) and alt>p['flight']['max_altitude']: errs.append(f"{label} altitude ({alt:g} m) exceeds maximum allowed altitude ({p['flight']['max_altitude']:g} m).")
   if math.isfinite(alt) and alt>p['geofence']['max_altitude']: errs.append(f"{label} altitude ({alt:g} m) exceeds geofence maximum ({p['geofence']['max_altitude']:g} m).")
   if not math.isfinite(speed) or speed<=0 or speed>p['flight']['max_speed']: errs.append(f"{label} speed ({speed:g} m/s) must be above 0 and at most {p['flight']['max_speed']:g} m/s.")
   dx=(lat-h['latitude'])*111320; dy=(lon-h['longitude'])*111320*math.cos(math.radians(lat))
   if p['geofence']['enabled'] and math.hypot(dx,dy)>radius: errs.append(f'Waypoint {i}: outside configured {radius} m geofence.')
  except (ValueError,TypeError,KeyError): errs.append(f'Waypoint {i}: coordinates, altitude, speed must be numeric.')
  if str(w.get('command','')).upper() not in valid: errs.append(f'Waypoint {i}: invalid command.')
 return {'valid':not errs,'errors':errs,'warnings':warnings,'parameters_source':'JSON CONFIG'}
@app.post('/api/missions/{ident}/validate')
async def validate_route(ident:str,user=__import__('fastapi').Depends(authdep)):
 r=fetchone('select items from missions where id=?',(ident,))
 if not r: raise HTTPException(404,'Mission not found')
 return validate(json.loads(r['items']))
@app.post('/api/missions/{ident}/upload')
async def upload(ident:str,user=__import__('fastapi').Depends(authdep)):
 r=fetchone('select items from missions where id=?',(ident,))
 if not r: raise HTTPException(404,'Mission not found')
 items=json.loads(r['items']); result=validate(items)
 if not result['valid']: raise HTTPException(422,detail=result)
 return await source().upload_mission(items)
@app.get('/api/flights')
async def flights(user=__import__('fastapi').Depends(authdep)): return [dict(r) for r in fetchall('select * from flights order by started desc')]
@app.get('/api/flights/{ident}')
async def flight(ident:str,user=__import__('fastapi').Depends(authdep)):
 r=fetchone('select * from flights where id=?',(ident,))
 if not r: raise HTTPException(404,'Flight not found')
 return dict(r)
@app.get('/api/alerts')
async def alerts(user=__import__('fastapi').Depends(authdep)): return [dict(r) for r in fetchall('select * from alerts order by id desc limit 100')]
@app.post('/api/alerts/{ident}/ack')
async def ack(ident:int,user=__import__('fastapi').Depends(authdep)):
 with db() as c:c.execute('update alerts set acknowledged=1 where id=?',(ident,))
 return {'ok':True}
@app.get('/api/config')
async def config(user=__import__('fastapi').Depends(authdep)):return {'drone':loadj('drone.json'),'data_source':('REAL DRONE' if os.getenv('DATA_SOURCE','simulation').lower()=='mavlink' else 'SIMULATION'),'simulation':loadj('simulation.json'),'parameters':loadj('parameters.json')}
@app.post('/api/config/source')
async def set_source(body:dict,user=__import__('fastapi').Depends(authdep)):
 mode=str(body.get('mode','')).lower()
 if mode not in ('simulation','mavlink'):raise HTTPException(400,'Choose simulation or real-drone adapter')
 os.environ['DATA_SOURCE']=mode
 return await source().get_status()
@app.get('/')
async def index():return FileResponse(ROOT/'frontend'/'index.html')
app.mount('/static',StaticFiles(directory=ROOT/'frontend'),name='static')
@app.get('/{page}.html')
async def pages(page:str):
 p=ROOT/'frontend'/f'{page}.html'
 if not p.exists():raise HTTPException(404)
 return FileResponse(p)
