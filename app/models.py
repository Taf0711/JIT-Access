from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, JSON, Enum as SQLEnum, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from app.db import Base


class UserRole(str, enum.Enum):
    REQUESTER = "requester"
    APPROVER = "approver"
    ADMIN = "admin"


class RequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class ResourceType(str, enum.Enum):
    DATABASE = "database"
    API = "api"
    SERVER = "server"
    SERVICE = "service"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.REQUESTER)
    api_key = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    access_requests = relationship("AccessRequest", back_populates="requester", foreign_keys="AccessRequest.user_id")
    approvals = relationship("AccessRequest", back_populates="approver", foreign_keys="AccessRequest.approved_by")


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    type = Column(SQLEnum(ResourceType), nullable=False)
    description = Column(Text, nullable=True)
    resource_metadata = Column(JSON, nullable=True, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    policies = relationship("Policy", back_populates="resource", cascade="all, delete-orphan")
    access_requests = relationship("AccessRequest", back_populates="resource")


class Policy(Base):
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False)
    name = Column(String, nullable=False)
    max_ttl_seconds = Column(Integer, nullable=False)  # Maximum time-to-live in seconds
    approval_rules = Column(JSON, nullable=True, default={})  # JSON with approval requirements
    time_window_restrictions = Column(JSON, nullable=True, default={})  # e.g., no access on weekends
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    resource = relationship("Resource", back_populates="policies")


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False)
    duration_seconds = Column(Integer, nullable=False)  # Requested duration
    justification = Column(Text, nullable=False)
    status = Column(SQLEnum(RequestStatus), nullable=False, default=RequestStatus.PENDING, index=True)
    is_break_glass = Column(Boolean, default=False, nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    denial_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    requester = relationship("User", back_populates="access_requests", foreign_keys=[user_id])
    approver = relationship("User", back_populates="approvals", foreign_keys=[approved_by])
    resource = relationship("Resource", back_populates="access_requests")
    grant = relationship("Grant", back_populates="access_request", uselist=False)
    approval_records = relationship("AccessRequestApproval", back_populates="access_request", cascade="all, delete-orphan")


class AccessRequestApproval(Base):
    __tablename__ = "access_request_approvals"
    __table_args__ = (
        UniqueConstraint("request_id", "approver_id", name="uq_access_request_approval"),
    )

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("access_requests.id"), nullable=False, index=True)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    access_request = relationship("AccessRequest", back_populates="approval_records")
    approver = relationship("User")


class Grant(Base):
    __tablename__ = "grants"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("access_requests.id"), nullable=False, unique=True)
    token_hash = Column(String, nullable=False, index=True)  # SHA256 hash of the JWT
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    access_request = relationship("AccessRequest", back_populates="grant")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False, index=True)  # e.g., REQUEST_CREATED, REQUEST_APPROVED, TOKEN_VALIDATED
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=True)
    request_id = Column(Integer, ForeignKey("access_requests.id"), nullable=True)
    event_metadata = Column(JSON, nullable=True, default={})  # Additional context
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    is_break_glass = Column(Boolean, default=False, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships (no back_populates to keep audit immutable and independent)
    user = relationship("User")
    resource = relationship("Resource")
    access_request = relationship("AccessRequest")
