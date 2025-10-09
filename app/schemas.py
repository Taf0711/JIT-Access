from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from app.models import UserRole, RequestStatus, ResourceType


# User schemas
class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: UserRole


class UserCreate(UserBase):
    pass


class User(UserBase):
    id: int
    api_key: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Resource schemas
class ResourceBase(BaseModel):
    name: str
    type: ResourceType
    description: Optional[str] = None
    resource_metadata: Optional[Dict[str, Any]] = {}


class ResourceCreate(ResourceBase):
    pass


class Resource(ResourceBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Policy schemas
class PolicyBase(BaseModel):
    resource_id: int
    name: str
    max_ttl_seconds: int = Field(gt=0, description="Maximum TTL in seconds")
    approval_rules: Optional[Dict[str, Any]] = {}
    time_window_restrictions: Optional[Dict[str, Any]] = {}


class PolicyCreate(PolicyBase):
    pass


class Policy(PolicyBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Access Request schemas
class AccessRequestCreate(BaseModel):
    resource_id: int
    duration_seconds: int = Field(gt=0, le=86400, description="Requested duration in seconds (max 24h)")
    justification: str = Field(min_length=10, description="Reason for access request")
    is_break_glass: bool = False


class AccessRequestUpdate(BaseModel):
    status: Optional[RequestStatus] = None
    denial_reason: Optional[str] = None


class AccessRequestApprove(BaseModel):
    pass


class AccessRequestDeny(BaseModel):
    denial_reason: str = Field(min_length=10, description="Reason for denial")


class AccessRequest(BaseModel):
    id: int
    user_id: int
    resource_id: int
    duration_seconds: int
    justification: str
    status: RequestStatus
    is_break_glass: bool
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    denial_reason: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AccessRequestDetail(AccessRequest):
    """Access request with related user and resource info"""
    requester: User
    resource: Resource
    approver: Optional[User] = None
    
    model_config = ConfigDict(from_attributes=True)


# Grant schemas
class Grant(BaseModel):
    id: int
    request_id: int
    expires_at: datetime
    revoked: bool
    revoked_at: Optional[datetime] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class GrantDetail(Grant):
    """Grant with request details"""
    access_request: AccessRequest
    
    model_config = ConfigDict(from_attributes=True)


# Audit Event schemas
class AuditEventCreate(BaseModel):
    event_type: str
    user_id: Optional[int] = None
    resource_id: Optional[int] = None
    request_id: Optional[int] = None
    event_metadata: Optional[Dict[str, Any]] = {}
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_break_glass: bool = False


class AuditEvent(BaseModel):
    id: int
    event_type: str
    user_id: Optional[int] = None
    resource_id: Optional[int] = None
    request_id: Optional[int] = None
    event_metadata: Optional[Dict[str, Any]] = {}
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_break_glass: bool
    timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Authentication
class CurrentUser(BaseModel):
    """Current authenticated user context"""
    id: int
    email: str
    name: str
    role: UserRole
    
    model_config = ConfigDict(from_attributes=True)

