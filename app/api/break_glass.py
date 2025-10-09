"""
Break-glass emergency access endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request as FastAPIRequest
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.db import get_db
from app import models, schemas
from app.dependencies import get_current_user, require_role
from app.services.audit import AuditService

router = APIRouter(prefix="/break-glass", tags=["Break-Glass"])


class BreakGlassApproval(BaseModel):
    """Additional break-glass approval"""
    pass


class BreakGlassRequestInfo(BaseModel):
    """Extended info for break-glass requests"""
    id: int
    user_id: int
    resource_id: int
    duration_seconds: int
    justification: str
    status: models.RequestStatus
    is_break_glass: bool
    approvals_count: int
    approvals_needed: int = 2
    approved_by: List[int] = []
    created_at: str
    
    class Config:
        from_attributes = True


@router.get("/requests", response_model=List[schemas.AccessRequestDetail])
def list_break_glass_requests(
    status_filter: models.RequestStatus = None,
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(require_role(models.UserRole.APPROVER)),
):
    """
    List all break-glass access requests
    
    Break-glass requests are flagged for emergency access and require
    dual approval (2 different approvers).
    """
    
    query = db.query(models.AccessRequest).filter(
        models.AccessRequest.is_break_glass == True
    )
    
    if status_filter:
        query = query.filter(models.AccessRequest.status == status_filter)
    
    # Order by most recent first
    query = query.order_by(models.AccessRequest.created_at.desc())
    
    requests = query.limit(50).all()
    
    return requests


@router.get("/requests/{request_id}/approvals")
def get_request_approvals(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(get_current_user),
):
    """
    Get all approval records for a break-glass request
    
    This shows the full approval chain for audit purposes.
    """
    
    access_request = db.query(models.AccessRequest).filter(
        models.AccessRequest.id == request_id
    ).first()
    
    if not access_request:
        raise HTTPException(status_code=404, detail="Access request not found")
    
    if not access_request.is_break_glass:
        raise HTTPException(status_code=400, detail="Not a break-glass request")
    
    # Get all approval audit events for this request
    approvals = db.query(models.AuditEvent).filter(
        models.AuditEvent.request_id == request_id,
        models.AuditEvent.event_type == "REQUEST_APPROVED"
    ).all()
    
    return {
        "request_id": request_id,
        "is_break_glass": True,
        "approvals_needed": 2,
        "approvals_count": len(approvals),
        "approvals": [
            {
                "approver_id": approval.user_id,
                "approved_at": approval.timestamp,
                "metadata": approval.event_metadata
            }
            for approval in approvals
        ]
    }


@router.post("/requests/{request_id}/second-approval", response_model=schemas.AccessRequest)
def provide_second_approval(
    request_id: int,
    request: FastAPIRequest,
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(require_role(models.UserRole.APPROVER)),
):
    """
    Provide the second approval for a break-glass request
    
    Break-glass requests require dual approval from two different approvers.
    This endpoint handles the second approval after the first one has been granted.
    """
    
    access_request = db.query(models.AccessRequest).filter(
        models.AccessRequest.id == request_id
    ).first()
    
    if not access_request:
        raise HTTPException(status_code=404, detail="Access request not found")
    
    if not access_request.is_break_glass:
        raise HTTPException(
            status_code=400,
            detail="This endpoint is only for break-glass requests"
        )
    
    # Check if request is pending
    if access_request.status != models.RequestStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Request is already {access_request.status.value}"
        )
    
    # Check if approver is not the requester
    if access_request.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot approve your own request")
    
    # Get existing approvals
    existing_approvals = db.query(models.AuditEvent).filter(
        models.AuditEvent.request_id == request_id,
        models.AuditEvent.event_type == "REQUEST_APPROVED"
    ).all()
    
    # Check if this approver already approved
    if any(approval.user_id == current_user.id for approval in existing_approvals):
        raise HTTPException(
            status_code=400,
            detail="You have already approved this request"
        )
    
    # Check if we need first approval or second
    if len(existing_approvals) == 0:
        # This is the first approval
        raise HTTPException(
            status_code=400,
            detail="Break-glass requests require dual approval. Use /api/v1/requests/{id}/approve for the first approval."
        )
    elif len(existing_approvals) == 1:
        # This is the second approval - finalize the request
        from datetime import datetime
        access_request.status = models.RequestStatus.APPROVED
        access_request.approved_by = current_user.id
        access_request.approved_at = datetime.utcnow()
        
        db.commit()
        db.refresh(access_request)
        
        # Audit log for second approval
        ip_address, user_agent = AuditService.extract_request_info(request)
        AuditService.log_event(
            db=db,
            event_type="BREAKGLASS_SECOND_APPROVAL",
            user_id=current_user.id,
            resource_id=access_request.resource_id,
            request_id=access_request.id,
            metadata={
                "second_approver_id": current_user.id,
                "first_approver_id": existing_approvals[0].user_id,
                "requester_id": access_request.user_id,
            },
            is_break_glass=True,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        return access_request
    else:
        raise HTTPException(
            status_code=400,
            detail="Request already has sufficient approvals"
        )


@router.get("/stats")
def get_break_glass_stats(
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(require_role(models.UserRole.ADMIN)),
):
    """
    Get statistics on break-glass access requests
    
    This provides insights into emergency access patterns.
    """
    
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    # Total break-glass requests
    total_requests = db.query(func.count(models.AccessRequest.id)).filter(
        models.AccessRequest.is_break_glass == True
    ).scalar()
    
    # Approved break-glass requests
    approved_requests = db.query(func.count(models.AccessRequest.id)).filter(
        models.AccessRequest.is_break_glass == True,
        models.AccessRequest.status == models.RequestStatus.APPROVED
    ).scalar()
    
    # Pending break-glass requests
    pending_requests = db.query(func.count(models.AccessRequest.id)).filter(
        models.AccessRequest.is_break_glass == True,
        models.AccessRequest.status == models.RequestStatus.PENDING
    ).scalar()
    
    # Denied break-glass requests
    denied_requests = db.query(func.count(models.AccessRequest.id)).filter(
        models.AccessRequest.is_break_glass == True,
        models.AccessRequest.status == models.RequestStatus.DENIED
    ).scalar()
    
    # Break-glass requests in last 24 hours
    yesterday = datetime.utcnow() - timedelta(hours=24)
    recent_requests = db.query(func.count(models.AccessRequest.id)).filter(
        models.AccessRequest.is_break_glass == True,
        models.AccessRequest.created_at >= yesterday
    ).scalar()
    
    # Most recent break-glass requests
    recent = db.query(models.AccessRequest).filter(
        models.AccessRequest.is_break_glass == True
    ).order_by(
        models.AccessRequest.created_at.desc()
    ).limit(10).all()
    
    return {
        "total_requests": total_requests,
        "approved": approved_requests,
        "pending": pending_requests,
        "denied": denied_requests,
        "last_24_hours": recent_requests,
        "recent_requests": [
            {
                "id": req.id,
                "user_id": req.user_id,
                "resource_id": req.resource_id,
                "status": req.status.value,
                "created_at": req.created_at.isoformat() if req.created_at else None,
            }
            for req in recent
        ]
    }

