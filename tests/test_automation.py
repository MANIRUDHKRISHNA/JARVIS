import json
from app.agent.automation import Automation,AutomationEngine,AutomationStore,AutomationState
from app.agent.execution import ExecutionEngine
def test_automation_persists_executes_and_honors_condition(tmp_path):
 store=AutomationStore(tmp_path/'a.db'); engine=AutomationEngine(store,ExecutionEngine(lambda tool,args:json.dumps({"success":True,"verified":True})))
 item=engine.create(Automation('daily',{'tool':'inspect'},trigger='manual')); assert engine.engine is not None; assert store.get(item.id).name=='daily'; assert engine.run(item.id)['success']; assert store.get(item.id).state is AutomationState.COMPLETED
 blocked=engine.create(Automation('wait',{},condition={'kind':'never'})); assert engine.run(blocked.id)['status']=='waiting'

def test_schedule_and_cancel_are_persistent_and_clock_injectable(tmp_path):
 store=AutomationStore(tmp_path/'a.db'); calls=[]; engine=AutomationEngine(store,ExecutionEngine(lambda tool,args:calls.append(tool) or json.dumps({'success':True,'verified':True})))
 item=engine.create(Automation('hourly',{'tool':'inspect'},trigger='schedule',schedule={'interval_seconds':10})); assert len(engine.poll(now=item.created_at+11))==1; assert calls; assert engine.cancel(item.id); assert store.get(item.id).state is AutomationState.CANCELLED
