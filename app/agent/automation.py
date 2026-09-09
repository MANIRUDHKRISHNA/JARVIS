"""Explicit, local automation storage and bounded dispatch."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from app.agent.execution import ExecutionEngine, ExecutionLimits, ExecutionStep
from app.agent.results import ToolResult

from app.agent.events import EventType, get_event_bus


class AutomationState(str, Enum):
    DISABLED="disabled"; SCHEDULED="scheduled"; WAITING="waiting"; RUNNING="running"; VERIFYING="verifying"; WAITING_FOR_CONFIRMATION="waiting_for_confirmation"; COMPLETED="completed"; FAILED="failed"; BLOCKED="blocked"; CANCELLED="cancelled"

@dataclass
class Automation:
    name: str; task: dict; trigger: str = "manual"; description: str = ""; enabled: bool = True
    schedule: dict | None = None; condition: dict | None = None; timeout: int = 120; max_retries: int = 1; max_steps: int = 12
    id: str = field(default_factory=lambda: uuid.uuid4().hex); state: AutomationState = AutomationState.SCHEDULED
    created_at: float = field(default_factory=time.time); updated_at: float = field(default_factory=time.time); last_run: float | None = None; next_run: float | None = None; run_count: int = 0; failure_count: int = 0


class AutomationStore:
    def __init__(self, path: str | Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db: db.execute("CREATE TABLE IF NOT EXISTS automations (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"); db.execute("CREATE TABLE IF NOT EXISTS automation_history (id INTEGER PRIMARY KEY, automation_id TEXT, payload TEXT NOT NULL)")
    def save(self, item: Automation) -> None:
        item.updated_at=time.time()
        with sqlite3.connect(self.path) as db: db.execute("INSERT OR REPLACE INTO automations VALUES (?,?)", (item.id,json.dumps({**asdict(item),"state":item.state.value})))
    def get(self, identifier: str) -> Automation | None:
        with sqlite3.connect(self.path) as db: row=db.execute("SELECT payload FROM automations WHERE id=?",(identifier,)).fetchone()
        if not row:return None
        data=json.loads(row[0]); data["state"]=AutomationState(data["state"]); return Automation(**data)
    def list(self) -> list[Automation]:
        with sqlite3.connect(self.path) as db: ids=[r[0] for r in db.execute("SELECT id FROM automations")]
        return [x for i in ids if (x:=self.get(i))]
    def delete(self, identifier: str) -> bool:
        with sqlite3.connect(self.path) as db:return db.execute("DELETE FROM automations WHERE id=?",(identifier,)).rowcount==1
    def history(self, item: Automation, result: dict) -> None:
        with sqlite3.connect(self.path) as db: db.execute("INSERT INTO automation_history (automation_id,payload) VALUES (?,?)",(item.id,json.dumps({"time":time.time(),"state":item.state.value,"result":result})))
    def set_enabled(self, identifier: str, enabled: bool) -> bool:
        item=self.get(identifier)
        if not item:return False
        item.enabled=enabled; item.state=AutomationState.SCHEDULED if enabled else AutomationState.DISABLED; self.save(item); return True


class AutomationEngine:
    """Poll-only scheduler: callers choose when to poll; no hidden background loop."""
    def __init__(self, store: AutomationStore, engine: ExecutionEngine, condition_check: Callable[[dict], bool] | None=None):
        self.store,self.engine,self.condition_check=store,engine,condition_check or (lambda _:False); self.events=get_event_bus(); self._running:set[str]=set()
    def create(self, item: Automation) -> Automation:
        if any(x.name==item.name and x.trigger==item.trigger and x.task==item.task for x in self.store.list()): raise ValueError("Duplicate automation")
        self.store.save(item); return item
    def cancel(self, identifier: str) -> bool:
        item=self.store.get(identifier)
        if not item:return False
        item.state=AutomationState.CANCELLED; item.enabled=False; self.store.save(item); self.events.publish(EventType.TASK_CANCELLED,automation_id=item.id); return True
    def poll(self, now: float | None = None) -> list[dict]:
        """Run due interval schedules once; caller owns timing/threading."""
        now=time.time() if now is None else now; results=[]
        for item in self.store.list():
            interval=(item.schedule or {}).get("interval_seconds")
            if item.enabled and item.trigger=="schedule" and isinstance(interval,(int,float)) and interval>0 and (item.last_run is None or now-item.last_run>=interval):
                results.append(self.run(item.id))
        return results
    def run(self, identifier: str) -> dict:
        item=self.store.get(identifier)
        if not item or not item.enabled:return {"success":False,"status":"unavailable","error":"Automation is missing or disabled."}
        if identifier in self._running:return {"success":False,"status":"blocked","error":"Automation is already running."}
        if item.condition and not self.condition_check(item.condition): item.state=AutomationState.WAITING; self.store.save(item); return {"success":True,"status":"waiting","verified":True}
        self._running.add(identifier); item.state=AutomationState.RUNNING; item.last_run=time.time(); self.events.publish(EventType.TASK_STARTED,automation_id=item.id,state=item.state.value)
        try:
            task = item.task
            if not isinstance(task.get("tool"), str):
                result={"success":False,"verified":False,"status":"failed","error":"Automation task requires a registered tool."}
            else:
                step=ExecutionStep(task.get("description", task["tool"]), task["tool"], dict(task.get("arguments", {})), retryable=bool(task.get("retryable")))
                report=self.engine.execute([step], task_id=f"automation-{item.id}")
                result={"success":report.success,"verified":report.success,"status":"completed" if report.success else "blocked" if step.status.value=="blocked" else "failed","steps":[{"id":step.id,"status":step.status.value,"verified":step.verification}],"error":step.error}
            status=str(result.get("status","failed")).lower(); item.run_count+=1
            item.state=AutomationState.COMPLETED if result.get("success") and result.get("verified",False) else AutomationState.BLOCKED if status=="blocked" else AutomationState.FAILED
            if item.state is AutomationState.FAILED: item.failure_count+=1; item.enabled=item.failure_count<=item.max_retries
            self.store.save(item); self.store.history(item,result); self.events.publish(EventType.TASK_FINISHED if item.state is AutomationState.COMPLETED else EventType.TASK_FAILED,automation_id=item.id,state=item.state.value)
            return result
        finally:self._running.discard(identifier)
