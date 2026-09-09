"""Local startup, database and feature-health hardening helpers."""
from __future__ import annotations
import os, shutil, sqlite3, sys, time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

class HealthState(str,Enum): HEALTHY="healthy"; DEGRADED="degraded"; UNAVAILABLE="unavailable"; FAILED="failed"; RECOVERING="recovering"
@dataclass
class FeatureFlags:
    voice:bool=True; browser:bool=True; spotify:bool=True; vision:bool=True; automations:bool=True; workflows:bool=True
class ReliabilityManager:
    def __init__(self,root:str|Path,flags:FeatureFlags|None=None):self.root=Path(root);self.flags=flags or FeatureFlags()
    def database_check(self,path:str|Path)->dict:
        target=Path(path)
        try:
            with sqlite3.connect(target) as db: result=db.execute("PRAGMA integrity_check").fetchone()[0]
            return {"state":HealthState.HEALTHY.value if result=="ok" else HealthState.FAILED.value,"detail":result,"path":str(target)}
        except sqlite3.Error as exc:return {"state":HealthState.FAILED.value,"detail":str(exc),"path":str(target)}
    def backup_database(self,path:str|Path,backup_dir:str|Path,retain:int=3)->dict:
        source,folder=Path(path),Path(backup_dir)
        if not source.exists():return {"success":False,"error":"Database does not exist."}
        folder.mkdir(parents=True,exist_ok=True); target=folder/f"{source.stem}.backup.sqlite"
        try:
            with sqlite3.connect(source) as read,sqlite3.connect(target) as write:read.backup(write)
            backups=sorted(folder.glob(f"{source.stem}.backup*.sqlite"),key=lambda p:p.stat().st_mtime,reverse=True)
            for old in backups[max(1,retain):]:old.unlink()
            return {"success":True,"verified":self.database_check(target)["state"]==HealthState.HEALTHY.value,"path":str(target)}
        except (sqlite3.Error,OSError) as exc:return {"success":False,"error":str(exc)}
    def doctor(self,databases:dict[str,str|Path]|None=None,registry=None)->dict:
        disk=shutil.disk_usage(self.root); checks=[{"name":"python","state":HealthState.HEALTHY.value,"detail":sys.version.split()[0]},{"name":"disk","state":HealthState.HEALTHY.value if disk.free>100*1024*1024 else HealthState.DEGRADED.value,"detail":f"{disk.free} bytes free"}]
        for name,path in (databases or {}).items():checks.append({"name":name,**self.database_check(path)})
        if registry:
            checks.extend({"name":x["name"],"state":HealthState.HEALTHY.value if x["available"] else HealthState.UNAVAILABLE.value,"detail":x["availability_reason"]} for x in registry.inventory())
        return {"success":all(x["state"]!=HealthState.FAILED.value for x in checks),"checks":checks,"features":self.flags.__dict__.copy()}
    def resource_state(self, active_tasks:int=0, worker_count:int=0)->dict:
        disk=shutil.disk_usage(self.root)
        state=HealthState.DEGRADED.value if disk.free<100*1024*1024 else HealthState.HEALTHY.value
        return {"state":state,"disk_free":disk.free,"active_tasks":active_tasks,"worker_count":worker_count,"policy":"pause optional automations and backups when degraded"}

class LifecycleCoordinator:
    """One owner for optional subsystem startup/shutdown; never hides failures."""
    def __init__(self,reliability:ReliabilityManager, automation=None, voice=None, model_manager=None):self.reliability,self.automation,self.voice,self.model_manager=reliability,automation,voice,model_manager;self.started=False;self.failures=[]
    def startup(self,databases=None,registry=None)->dict:
        report=self.reliability.doctor(databases,registry);self.started=True;return report
    def shutdown(self)->dict:
        errors=[]
        for component,method in ((self.voice,"stop"),(self.model_manager,"stop")):
            if component and getattr(component,"running",True):
                try:getattr(component,method)()
                except Exception as exc:errors.append(str(exc))
        self.started=False;return {"success":not errors,"errors":errors,"verified":not errors}
    def record_worker_crash(self,subsystem:str,error:Exception,task_id:str|None=None)->dict:
        event={"subsystem":subsystem,"error":str(error),"task_id":task_id,"timestamp":time.time(),"state":HealthState.DEGRADED.value};self.failures.append(event);return event
