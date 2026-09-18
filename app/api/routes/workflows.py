from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_membership
from app.db.session import get_db
from app.models import Role, User, Workflow, WorkflowVersion
from app.schemas import (
    WorkflowCreate,
    WorkflowRead,
    WorkflowVersionCreate,
    WorkflowVersionRead,
)
from app.services.audit import write_audit
from app.services.workflow_validator import (
    WorkflowValidationError,
    canonical_checksum,
    validate_workflow,
)

router = APIRouter(tags=["workflows"])


@router.post(
    "/organizations/{organization_id}/workflows",
    response_model=WorkflowRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow(
    organization_id: UUID,
    payload: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Workflow:
    await require_membership(db, user.id, organization_id)
    workflow = Workflow(
        organization_id=organization_id,
        name=payload.name,
        created_by=user.id,
    )
    db.add(workflow)
    await db.flush()
    await write_audit(
        db,
        organization_id=organization_id,
        user_id=user.id,
        action="workflow.created",
        entity_type="workflow",
        entity_id=str(workflow.id),
    )
    await db.commit()
    await db.refresh(workflow)
    return workflow


@router.get("/organizations/{organization_id}/workflows", response_model=list[WorkflowRead])
async def list_workflows(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Workflow]:
    await require_membership(db, user.id, organization_id)
    result = await db.execute(
        select(Workflow)
        .where(Workflow.organization_id == organization_id)
        .order_by(Workflow.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/workflows/{workflow_id}/versions",
    response_model=WorkflowVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    workflow_id: UUID,
    payload: WorkflowVersionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkflowVersion:
    workflow = await db.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await require_membership(
        db,
        user.id,
        workflow.organization_id,
        {Role.owner.value, Role.admin.value, Role.member.value},
    )
    try:
        validate_workflow(payload.definition)
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    latest = await db.scalar(
        select(func.max(WorkflowVersion.version)).where(WorkflowVersion.workflow_id == workflow_id)
    )
    version = WorkflowVersion(
        workflow_id=workflow_id,
        version=(latest or 0) + 1,
        definition=payload.definition,
        checksum=canonical_checksum(payload.definition),
        created_by=user.id,
    )
    db.add(version)
    await db.flush()
    await write_audit(
        db,
        organization_id=workflow.organization_id,
        user_id=user.id,
        action="workflow.version_created",
        entity_type="workflow",
        entity_id=str(workflow.id),
        details={"version": version.version, "checksum": version.checksum},
    )
    await db.commit()
    await db.refresh(version)
    return version


@router.post("/workflows/{workflow_id}/versions/{version}/activate", response_model=WorkflowRead)
async def activate_version(
    workflow_id: UUID,
    version: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Workflow:
    workflow = await db.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await require_membership(
        db,
        user.id,
        workflow.organization_id,
        {Role.owner.value, Role.admin.value},
    )
    exists = await db.scalar(
        select(WorkflowVersion.id).where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version == version,
        )
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="Workflow version not found")

    workflow.active_version = version
    await write_audit(
        db,
        organization_id=workflow.organization_id,
        user_id=user.id,
        action="workflow.activated",
        entity_type="workflow",
        entity_id=str(workflow.id),
        details={"version": version},
    )
    await db.commit()
    await db.refresh(workflow)
    return workflow
