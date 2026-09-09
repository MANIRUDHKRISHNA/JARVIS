"""Regression tests for the one Brain-owned production execution boundary."""

from app.agent.automation import AutomationStore
from app.agent.pipeline import AgentPipeline
from app.agent.workflows import WorkflowStore


def test_pipeline_factories_share_the_brain_execution_boundary(tmp_path):
    pipeline = AgentPipeline()

    automation = pipeline.create_automation_engine(AutomationStore(tmp_path / "automation.db"))
    workflow = pipeline.create_workflow_engine(WorkflowStore(tmp_path / "workflow.db"))
    autonomous = pipeline.create_autonomous_task_manager()
    coding = pipeline.create_coding_workflow(tmp_path)
    workbench = pipeline.create_workbench(tmp_path)
    executor = pipeline.create_executor()

    assert automation.engine is pipeline.execution
    assert workflow.engine is pipeline.execution
    assert autonomous.engine is pipeline.execution
    assert coding.engine is pipeline.execution
    assert coding.registry is pipeline.registry
    assert workbench.workflow.engine is pipeline.execution
    assert workbench.engine is pipeline.execution
    assert workbench.registry is pipeline.registry
    assert workbench.workflow.security is pipeline.security
    assert executor.execution is pipeline.execution

    assert pipeline.registry.get("compile_project") is not None


def test_pipeline_factory_keeps_brain_security_and_registry_as_the_owner(tmp_path):
    pipeline = AgentPipeline()
    coding = pipeline.create_coding_workflow(tmp_path, dry_run=True)

    assert coding.registry is pipeline.registry
    assert coding.security is pipeline.security
