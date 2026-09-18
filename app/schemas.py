from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(RegisterRequest):
    pass


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    created_at: datetime


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    created_at: datetime


class MembershipCreate(BaseModel):
    user_id: UUID
    role: str = Field(pattern="^(admin|member)$")


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)


class WorkflowVersionCreate(BaseModel):
    definition: dict


class WorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    name: str
    active_version: int | None
    created_at: datetime


class WorkflowVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workflow_id: UUID
    version: int
    definition: dict
    checksum: str
    created_at: datetime


class ExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    workflow_id: UUID
    workflow_version_id: UUID
    trigger_type: str
    status: str
    idempotency_key: str
    input_data: dict
    output_data: dict | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ExecutionStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    node_id: str
    node_type: str
    status: str
    attempt: int
    output_data: dict | None
    error: str | None
    duration_ms: int | None


class SecretCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    value: str = Field(min_length=1, max_length=10000)


class SecretRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    created_at: datetime


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    action: str
    entity_type: str
    entity_id: str
    details: dict
    created_at: datetime
