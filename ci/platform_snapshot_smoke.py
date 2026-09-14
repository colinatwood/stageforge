#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, platform, subprocess, sys, threading, time, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BACKEND=ROOT/'backend'
sys.path.insert(0,str(BACKEND))
EXPECTED={'backend/session_channel.py':'084aba7954394bb2732e9770312e25e2d0a23aceaa91d2a2c78513648e695ff7','backend/local_ipc.py':'fb8bb0337c312253400125b7abbc6820c74cf42177ba0461d00767b61e4639cc','backend/windows_named_pipe.py':'0a6581b87a2d153b4090bbdded963872fcac9d665f2ae47e5a74c8355f9f0f8b','backend/audio_endpoint_evidence.py':'7ea22c6d70e4406196e1ac531a82c50eb433761d9fb1cf92a892c5da6c5b6402'}
def sha(p): return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def verify_snapshot():
 actual={p:sha(p) for p in EXPECTED}
 if actual!=EXPECTED: raise RuntimeError(f'checkpoint 69 module hash mismatch: {actual}')
 return actual
def windows_pipe():
 from multiprocessing.connection import Client
 from local_ipc import WindowsNamedPipeIpcServer
 from session_channel import AuthenticatedSessionChannel
 import csv,io
 row=next(csv.reader(io.StringIO(subprocess.check_output(['whoami.exe','/user','/fo','csv','/nh'],text=True).strip())))
 sid=row[1].upper(); name=rf'\\.\pipe\StageForge\CI-{uuid.uuid4().hex}'
 key=hashlib.sha256(b'stageforge-github-bootstrap').digest(); cluster='11'*16; session='22'*32
 def channel(): return AuthenticatedSessionChannel(key,cluster,session,{7},send_direction='server',receive_direction='client')
 server=WindowsNamedPipeIpcServer(name,channel,lambda c,p:b'github-ci:'+p,max_requests=1,allowed_sids=(sid,),allow_administrators=False)
 server.start(); errors=[]
 t=threading.Thread(target=lambda: _serve(server,errors),daemon=True); t.start()
 conn=None; deadline=time.monotonic()+10
 while conn is None and time.monotonic()<deadline:
  try: conn=Client(name,family='AF_PIPE')
  except OSError: time.sleep(.05)
 if conn is None: server.close(); raise RuntimeError('pipe connect timeout')
 client=AuthenticatedSessionChannel(key,cluster,session,{7},send_direction='client',receive_direction='server')
 conn.send_bytes(client.encode(7,b'ping')); decoded=client.decode(conn.recv_bytes()); conn.close(); t.join(10); server.close()
 if errors: raise errors[0]
 if decoded['payload']!=b'github-ci:ping': raise RuntimeError('unexpected pipe response')
 return {'kernelDaclAndAuthorizedRoundtripQualified':True,'sidHash':hashlib.sha256(sid.encode()).hexdigest(),'unauthorizedClientDenialQualified':False}
def _serve(server,errors):
 try: server.serve_once()
 except BaseException as e: errors.append(e)
def mac_audio():
 from audio_endpoint_evidence import macos_endpoint_probe
 def run(cmd): return json.loads(subprocess.check_output(cmd,text=True,encoding='utf-8',errors='replace'))
 endpoints,drivers=macos_endpoint_probe(run)
 return {'coreAudioProbeQualified':True,'endpointCount':len(endpoints),'driverRecordCount':len(drivers),'physicalInterfaceQualified':False}
def main():
 report={'documentType':'org.upp.github-platform-module-smoke','schemaVersion':1,'host':{'os':platform.system(),'release':platform.release(),'architecture':platform.machine()},'physicalOutputsArmed':False,'physicalHardwareQualified':False,'trackedFiles':verify_snapshot(),'checks':{}}
 if platform.system()=='Windows': report['checks']['windowsNamedPipe']=windows_pipe()
 elif platform.system()=='Darwin': report['checks']['macosAudioEvidence']=mac_audio()
 else: report['checks']['linuxImportReference']={'qualified':True}
 out=Path(os.environ.get('STAGEFORGE_CI_EVIDENCE','platform-module-smoke.json')); out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); print(out.read_text()); return 0
if __name__=='__main__': raise SystemExit(main())
