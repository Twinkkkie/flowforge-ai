from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_membership
from app.db.session import get_db
from app.models import Execution, ExecutionStep, User, Workflow, WorkflowVersion
from app.schemas import ExecutionRead, ExecutionStepRead
from app.services.audit import write_audit
from app.worker.tasks import run_execution

router = APIRouter(tags=["executions"])


async def _active_version(db: AsyncSession, workflow: Workflow) -> WorkflowVersion:
    if workflow.active_version is None:
        raise HTTPException(status_code=409, detail="Workflow has no active version")
    version = await db.scalar(
        select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == workflow.id,
            WorkflowVersion.version == workflow.active_version,
        )
    )
    if version is None:
        raise HTTPException(status_code=409, detail="Active workflow version is missing")
    return version


@router.post(
    "/workflows/{workflow_id}/execute",
    response_model=ExecutionRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute_manually(
    workflow_id: UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Execution:
    workflow = await db.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await require_membership(db, user.id, workflow.organization_id)
    version = await _active_version(db, workflow)

    execution = Execution(
        organization_id=workflow.organization_id,
        workflow_id=workflow.id,
        workflow_version_id=version.id,
        trigger_type="manual",
        idempotency_key=f"manual:{uuid4()}",
        input_data=payload,
    )
    db.add(execution)
    await db.flush()
    await write_audit(
        db,
        organization_id=workflow.organization_id,
        user_id=user.id,
        action="execution.queued",
        entity_type="execution",
        entity_id=str(execution.id),
        details={"trigger": "manual", "workflow_version": version.version},
    )
    await db.commit()
    await db.refresh(execution)
    run_execution.delay(str(execution.id))
    return execution


@router.get(
    "/organizations/{organization_id}/executions",
    response_model=list[ExecutionRead],
)
async def list_executions(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Execution]:
    await require_membership(db, user.id, organization_id)
    result = await db.execute(
        select(Execution)
        .where(Execution.organization_id == organization_id)
        .order_by(Execution.created_at.desc())
        .limit(100)
    )
    return list(result.scalars().all())


@router.get("/executions/{execution_id}", response_model=ExecutionRead)
async def get_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Execution:
    execution = await db.get(Execution, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    await require_membership(db, user.id, execution.organization_id)
    return execution


@router.get("/executions/{execution_id}/steps", response_model=list[ExecutionStepRead])
async def get_execution_steps(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ExecutionStep]:
    execution = await db.get(Execution, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    await require_membership(db, user.id, execution.organization_id)
    result = await db.execute(
        select(ExecutionStep)
        .where(ExecutionStep.execution_id == execution_id)
        .order_by(ExecutionStep.created_at.asc())
    )
    return list(result.scalars().all())
