from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_membership
from app.db.session import get_db
from app.models import Membership, Organization, Role, User
from app.schemas import MembershipCreate, OrganizationCreate, OrganizationRead
from app.services.audit import write_audit

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Organization:
    organization = Organization(name=payload.name, created_by=user.id)
    db.add(organization)
    await db.flush()
    db.add(
        Membership(
            organization_id=organization.id,
            user_id=user.id,
            role=Role.owner.value,
        )
    )
    await write_audit(
        db,
        organization_id=organization.id,
        user_id=user.id,
        action="organization.created",
        entity_type="organization",
        entity_id=str(organization.id),
    )
    await db.commit()
    await db.refresh(organization)
    return organization


@router.get("", response_model=list[OrganizationRead])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Organization]:
    result = await db.execute(
        select(Organization)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user.id)
        .order_by(Organization.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{organization_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def add_member(
    organization_id: UUID,
    payload: MembershipCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await require_membership(
        db,
        user.id,
        organization_id,
        {Role.owner.value, Role.admin.value},
    )
    if await db.get(User, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    if await db.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == payload.user_id,
        )
    ):
        raise HTTPException(status_code=409, detail="User already belongs to organization")

    db.add(
        Membership(
            organization_id=organization_id,
            user_id=payload.user_id,
            role=payload.role,
        )
    )
    await write_audit(
        db,
        organization_id=organization_id,
        user_id=user.id,
        action="membership.created",
        entity_type="user",
        entity_id=str(payload.user_id),
        details={"role": payload.role},
    )
    await db.commit()
