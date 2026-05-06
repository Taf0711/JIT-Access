from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from app import models, schemas
from fastapi import Request
from app.services.metrics import metrics_service


class AuditService:
    """Service for creating audit events"""
    
    @staticmethod
    def log_event(
        db: Session,
        event_type: str,
        user_id: Optional[int] = None,
        resource_id: Optional[int] = None,
        request_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_break_glass: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> models.AuditEvent:
        """Create an audit event"""
        audit_event = models.AuditEvent(
            event_type=event_type,
            user_id=user_id,
            resource_id=resource_id,
            request_id=request_id,
            event_metadata=metadata or {},
            is_break_glass=is_break_glass,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(audit_event)
        db.commit()
        db.refresh(audit_event)
        metrics_service.record_audit_event(event_type, is_break_glass)
        return audit_event
    
    @staticmethod
    def extract_request_info(request: Request) -> tuple[Optional[str], Optional[str]]:
        """Extract IP address and user agent from FastAPI request"""
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        return ip_address, user_agent
