from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_membership
from app.db.session import get_db
from app.models import Role, Secret, User
from app.schemas import SecretCreate, SecretRead
from app.services.audit import write_audit
from app.services.secrets import encrypt_secret

router = APIRouter(tags=["secrets"])


@router.post(
    "/organizations/{organization_id}/secrets",
    response_model=SecretRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_secret(
    organization_id: UUID,
    payload: SecretCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Secret:
    await require_membership(
        db,
        user.id,
        organization_id,
        {Role.owner.value, Role.admin.value},
    )
    if await db.scalar(
        select(Secret).where(
            Secret.organization_id == organization_id,
            Secret.name == payload.name,
        )
    ):
        raise HTTPException(status_code=409, detail="Secret name already exists")

    secret = Secret(
        organization_id=organization_id,
        name=payload.name,
        ciphertext=encrypt_secret(payload.value),
    )
    db.add(secret)
    await db.flush()
    await write_audit(
        db,
        organization_id=organization_id,
        user_id=user.id,
        action="secret.created",
        entity_type="secret",
        entity_id=str(secret.id),
        details={"name": secret.name},
    )
    await db.commit()
    await db.refresh(secret)
    return secret


@router.get(
    "/organizations/{organization_id}/secrets",
    response_model=list[SecretRead],
)
async def list_secrets(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Secret]:
    await require_membership(db, user.id, organization_id)
    result = await db.execute(
        select(Secret)
        .where(Secret.organization_id == organization_id)
        .order_by(Secret.created_at.desc())
    )
    return list(result.scalars().all())
