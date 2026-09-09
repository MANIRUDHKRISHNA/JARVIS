"""Persistent, declarative workflow recipes executed by the shared engine."""
from __future__ import annotations
import json, sqlite3, time, uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable
from app.agent.execution import ExecutionEngine, ExecutionLimits, ExecutionStep

@dataclass
class Workflow:
    name:str; steps:list[dict]; description:str=""; inputs:dict=field(default_factory=dict); version:int=1; id:str=field(default_factory=lambda:uuid.uuid4().hex); created_at:float=field(default_factory=time.time); updated_at:float=field(default_factory=time.time)

class WorkflowStore:
    def __init__(self,path:str|Path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:db.execute("CREATE TABLE IF NOT EXISTS workflows (id TEXT PRIMARY KEY,payload TEXT NOT NULL)")
    def save(self,w:Workflow):
        w.updated_at=time.time()
        with sqlite3.connect(self.path) as db:db.execute("INSERT OR REPLACE INTO workflows VALUES (?,?)",(w.id,json.dumps(asdict(w))))
    def get(self,identifier:str)->Workflow|None:
        with sqlite3.connect(self.path) as db:r=db.execute("SELECT payload FROM workflows WHERE id=?",(identifier,)).fetchone()
        return Workflow(**json.loads(r[0])) if r else None
    def list(self)->list[Workflow]:
        with sqlite3.connect(self.path) as db: ids=[r[0] for r in db.execute("SELECT id FROM workflows")]
        return [w for identifier in ids if (w:=self.get(identifier))]
    def revise(self,identifier:str,steps:list[dict],description:str|None=None)->Workflow|None:
        current=self.get(identifier)
        if not current:return None
        current.steps=steps; current.version+=1
        if description is not None:current.description=description
        self.save(current);return current

class WorkflowEngine:
    def __init__(self,store:WorkflowStore, engine: ExecutionEngine):self.store,self.engine=store,engine
    def validate(self,w:Workflow,inputs:dict)->str|None:
        for name,schema in w.inputs.items():
            if schema.get("required") and name not in inputs:return f"Missing workflow input: {name}"
        for step in w.steps:
            if not isinstance(step.get("tool"),str):return "Every step requires a registered tool name."
        return None
    def run(self,identifier:str,inputs:dict|None=None,dry_run:bool=False)->dict:
        w=self.store.get(identifier); inputs=inputs or {}
        if not w:return {"success":False,"status":"failed","error":"Workflow not found."}
        error=self.validate(w,inputs)
        if error:return {"success":False,"status":"failed","error":error}
        planned=[]
        for item in w.steps:
            if item.get("when") == "previous_failed" and planned: continue
            args={k:(inputs.get(v[1:]) if isinstance(v,str) and v.startswith("$") else v) for k,v in item.get("arguments",{}).items()}
            planned.append(ExecutionStep(item.get("description",item["tool"]),item["tool"],args,retryable=bool(item.get("retryable"))))
        if dry_run:return {"success":True,"verified":True,"status":"dry_run","workflow_version":w.version,"steps":[s.description for s in planned]}
        report=self.engine.execute(planned)
        return {"success":report.success,"verified":report.success,"status":"completed" if report.success else "partial" if any(s.verification for s in report.steps) else "failed","workflow_version":w.version,"steps":[{"id":s.id,"status":s.status.value,"verified":s.verification} for s in report.steps]}
