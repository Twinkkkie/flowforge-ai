from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def write_audit(
    db: AsyncSession,
    *,
    organization_id: UUID,
    user_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
    )
