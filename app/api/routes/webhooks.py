import hashlib
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Execution, Workflow, WorkflowVersion
from app.schemas import ExecutionRead
from app.services.idempotency import claim_idempotency_key
from app.worker.tasks import run_execution

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/{workflow_id}",
    response_model=ExecutionRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def webhook_trigger(
    workflow_id: UUID,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
) -> Execution:
    workflow = await db.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if workflow.active_version is None:
        raise HTTPException(status_code=409, detail="Workflow has no active version")

    raw = await request.body()
    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Webhook body must be JSON") from exc

    key = idempotency_key or hashlib.sha256(raw).hexdigest()
    claimed = await claim_idempotency_key(str(workflow_id), key)
    if not claimed:
        existing = await db.scalar(
            select(Execution).where(
                Execution.workflow_id == workflow_id,
                Execution.idempotency_key == key,
            )
        )
        if existing is not None:
            return existing
        raise HTTPException(status_code=409, detail="Duplicate webhook is already being processed")

    version = await db.scalar(
        select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version == workflow.active_version,
        )
    )
    if version is None:
        raise HTTPException(status_code=409, detail="Active workflow version is missing")

    execution = Execution(
        organization_id=workflow.organization_id,
        workflow_id=workflow.id,
        workflow_version_id=version.id,
        trigger_type="webhook",
        idempotency_key=key,
        input_data=payload,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    run_execution.delay(str(execution.id))
    return execution
