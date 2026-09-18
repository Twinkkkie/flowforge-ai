from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.runner import WorkflowExecutionError, run_workflow
from app.models import Execution, ExecutionStatus, ExecutionStep, WorkflowVersion


async def _persist_outcomes(
    db: AsyncSession,
    execution_id: UUID,
    outcomes,
) -> None:
    for outcome in outcomes:
        db.add(
            ExecutionStep(
                execution_id=execution_id,
                node_id=outcome.node_id,
                node_type=outcome.node_type,
                status=outcome.status,
                attempt=outcome.attempt,
                input_data=outcome.input_data,
                output_data=outcome.output_data,
                error=outcome.error,
                duration_ms=outcome.duration_ms,
            )
        )


async def execute_workflow_run(db: AsyncSession, execution_id: UUID) -> Execution:
    execution = await db.get(Execution, execution_id)
    if execution is None:
        raise ValueError("Execution not found")

    version = await db.get(WorkflowVersion, execution.workflow_version_id)
    if version is None:
        raise ValueError("Workflow version not found")

    execution.status = ExecutionStatus.running.value
    execution.started_at = datetime.now(UTC)
    await db.commit()

    try:
        result = await run_workflow(version.definition, execution.input_data)
        await _persist_outcomes(db, execution.id, result.outcomes)
        execution.output_data = result.output
        execution.status = ExecutionStatus.succeeded.value
        execution.finished_at = datetime.now(UTC)
        await db.commit()
        return execution
    except WorkflowExecutionError as exc:
        await _persist_outcomes(db, execution.id, exc.outcomes)
        execution.status = ExecutionStatus.failed.value
        execution.error = str(exc)
        execution.finished_at = datetime.now(UTC)
        await db.commit()
        return execution
