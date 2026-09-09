import json
from app.agent.execution import ExecutionEngine
from app.agent.workflows import Workflow,WorkflowEngine,WorkflowStore
def test_workflow_parameter_validation_dry_run_and_execution(tmp_path):
 store=WorkflowStore(tmp_path/'w.db'); w=Workflow('check',[{'tool':'echo','arguments':{'text':'$value'}}],inputs={'value':{'required':True}});store.save(w);engine=WorkflowEngine(store,ExecutionEngine(lambda tool,args:json.dumps({'success':True,'verified':True})))
 assert engine.engine is not None; assert not engine.run(w.id,{})['success']; assert engine.run(w.id,{'value':'ok'},dry_run=True)['status']=='dry_run'; assert engine.run(w.id,{'value':'ok'})['success']
 assert store.revise(w.id, w.steps).version == 2
