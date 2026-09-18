from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_membership
from app.db.session import get_db
from app.models import AuditLog, Role, User
from app.schemas import AuditRead

router = APIRouter(tags=["audit"])


@router.get(
    "/organizations/{organization_id}/audit",
    response_model=list[AuditRead],
)
async def list_audit(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AuditLog]:
    await require_membership(
        db,
        user.id,
        organization_id,
        {Role.owner.value, Role.admin.value},
    )
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.organization_id == organization_id)
        .order_by(AuditLog.created_at.desc())
        .limit(200)
    )
    return list(result.scalars().all())
