from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query, Request as FastAPIRequest
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from datetime import datetime, timedelta

from app.db import get_db
from app import models, schemas
from app.dependencies import get_current_user, require_role
from app.services.audit import AuditService
from app.services.notifications import slack_service
from app.services import approvals as approval_service
from app.services.policy import policy_service
from app.services.metrics import metrics_service

router = APIRouter(prefix="/requests", tags=["Access Requests"])


@router.post("", response_model=schemas.AccessRequest, status_code=status.HTTP_201_CREATED)
async def create_access_request(
    request_data: schemas.AccessRequestCreate,
    request: FastAPIRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(get_current_user),
):
    """Submit a new access request"""
    
    # Verify resource exists
    resource = db.query(models.Resource).filter(models.Resource.id == request_data.resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    policy = db.query(models.Policy).filter(models.Policy.resource_id == request_data.resource_id).first()
    policy_config = {
        "max_ttl_seconds": policy.max_ttl_seconds if policy else 86400,
        "approval_rules": policy.approval_rules if policy else {},
        "time_window_restrictions": policy.time_window_restrictions if policy else {},
    }
    allowed, violations = await policy_service.evaluate_request_policy(
        user_id=current_user.id,
        user_role=current_user.role.value,
        resource_id=resource.id,
        resource_type=resource.type.value,
        duration_seconds=request_data.duration_seconds,
        is_break_glass=request_data.is_break_glass,
        resource_metadata=resource.resource_metadata or {},
        policy_config=policy_config,
    )
    if not allowed:
        ip_address, user_agent = AuditService.extract_request_info(request)
        AuditService.log_event(
            db=db,
            event_type="REQUEST_POLICY_DENIED",
            user_id=current_user.id,
            resource_id=resource.id,
            metadata={
                "duration_seconds": request_data.duration_seconds,
                "justification": request_data.justification,
                "violations": violations,
            },
            is_break_glass=request_data.is_break_glass,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        metrics_service.record_access_request(
            "denied",
            resource.type.value,
            request_data.is_break_glass,
        )
        raise HTTPException(
            status_code=400,
            detail="; ".join(violations) if violations else "Request denied by policy"
        )
    
    # Create access request
    access_request = models.AccessRequest(
        user_id=current_user.id,
        resource_id=request_data.resource_id,
        duration_seconds=request_data.duration_seconds,
        justification=request_data.justification,
        is_break_glass=request_data.is_break_glass,
        status=models.RequestStatus.PENDING,
    )
    
    db.add(access_request)
    db.commit()
    db.refresh(access_request)
    metrics_service.record_access_request(
        access_request.status.value,
        resource.type.value,
        access_request.is_break_glass,
    )
    
    # Audit log
    ip_address, user_agent = AuditService.extract_request_info(request)
    AuditService.log_event(
        db=db,
        event_type="REQUEST_CREATED",
        user_id=current_user.id,
        resource_id=resource.id,
        request_id=access_request.id,
        metadata={
            "duration_seconds": request_data.duration_seconds,
            "justification": request_data.justification,
        },
        is_break_glass=request_data.is_break_glass,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    background_tasks.add_task(
        slack_service.notify_new_request,
        request_id=access_request.id,
        requester_name=current_user.name,
        resource_name=resource.name,
        duration_hours=request_data.duration_seconds / 3600,
        justification=request_data.justification,
        is_break_glass=request_data.is_break_glass,
    )
    
    return access_request


@router.get("", response_model=List[schemas.AccessRequestDetail])
def list_access_requests(
    status_filter: Optional[models.RequestStatus] = Query(None, alias="status"),
    user_id: Optional[int] = Query(None),
    resource_id: Optional[int] = Query(None),
    is_break_glass: Optional[bool] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(get_current_user),
):
    """List access requests with filtering"""
    
    query = db.query(models.AccessRequest)
    
    # Non-admin users can only see their own requests or requests they can approve
    if current_user.role != models.UserRole.ADMIN:
        if current_user.role == models.UserRole.APPROVER:
            # Approvers can see requests they can approve and their own requests
            query = query.filter(
                or_(
                    models.AccessRequest.user_id == current_user.id,
                    models.AccessRequest.status == models.RequestStatus.PENDING
                )
            )
        else:
            # Requesters can only see their own
            query = query.filter(models.AccessRequest.user_id == current_user.id)
    
    # Apply filters
    if status_filter:
        query = query.filter(models.AccessRequest.status == status_filter)
    if user_id is not None:
        query = query.filter(models.AccessRequest.user_id == user_id)
    if resource_id is not None:
        query = query.filter(models.AccessRequest.resource_id == resource_id)
    if is_break_glass is not None:
        query = query.filter(models.AccessRequest.is_break_glass == is_break_glass)
    
    # Order by most recent first
    query = query.order_by(models.AccessRequest.created_at.desc())
    
    # Pagination
    requests = query.offset(offset).limit(limit).all()
    
    return requests


@router.get("/{request_id}", response_model=schemas.AccessRequestDetail)
def get_access_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(get_current_user),
):
    """Get a specific access request"""
    
    access_request = db.query(models.AccessRequest).filter(models.AccessRequest.id == request_id).first()
    if not access_request:
        raise HTTPException(status_code=404, detail="Access request not found")
    
    # Check permissions
    if current_user.role not in [models.UserRole.ADMIN, models.UserRole.APPROVER]:
        if access_request.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to view this request")
    
    return access_request


@router.post("/{request_id}/approve", response_model=schemas.AccessRequest)
async def approve_access_request(
    request_id: int,
    request: FastAPIRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(require_role(models.UserRole.APPROVER)),
):
    """Approve an access request"""
    
    access_request = db.query(models.AccessRequest).filter(models.AccessRequest.id == request_id).first()
    if not access_request:
        raise HTTPException(status_code=404, detail="Access request not found")
    
    access_request, _approvals_count, _approvals_required, finalized = await approval_service.approve_access_request(
        db=db,
        access_request=access_request,
        current_user=current_user,
        request=request,
    )
    
    if finalized:
        requester = db.query(models.User).filter(models.User.id == access_request.user_id).first()
        resource_obj = db.query(models.Resource).filter(models.Resource.id == access_request.resource_id).first()
        if resource_obj:
            metrics_service.record_access_request(
                access_request.status.value,
                resource_obj.type.value,
                access_request.is_break_glass,
            )
        background_tasks.add_task(
            slack_service.notify_request_approved,
            request_id=access_request.id,
            requester_name=requester.name if requester else "Unknown",
            approver_name=current_user.name,
            resource_name=resource_obj.name if resource_obj else "Unknown",
            is_break_glass=access_request.is_break_glass,
        )
    
    return access_request


@router.post("/{request_id}/deny", response_model=schemas.AccessRequest)
def deny_access_request(
    request_id: int,
    deny_data: schemas.AccessRequestDeny,
    request: FastAPIRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(require_role(models.UserRole.APPROVER)),
):
    """Deny an access request"""
    
    access_request = db.query(models.AccessRequest).filter(models.AccessRequest.id == request_id).first()
    if not access_request:
        raise HTTPException(status_code=404, detail="Access request not found")
    
    # Verify request is pending
    if access_request.status != models.RequestStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Request is already {access_request.status.value}")
    
    # Update request
    access_request.status = models.RequestStatus.DENIED
    access_request.approved_by = current_user.id
    access_request.approved_at = datetime.utcnow()
    access_request.denial_reason = deny_data.denial_reason
    
    db.commit()
    db.refresh(access_request)

    resource_obj = db.query(models.Resource).filter(models.Resource.id == access_request.resource_id).first()
    metrics_service.record_access_request(
        access_request.status.value,
        resource_obj.type.value if resource_obj else "unknown",
        access_request.is_break_glass,
    )
    metrics_service.record_approval(
        current_user.role.value,
        access_request.is_break_glass,
        "denied",
    )
    
    # Audit log
    ip_address, user_agent = AuditService.extract_request_info(request)
    AuditService.log_event(
        db=db,
        event_type="REQUEST_DENIED",
        user_id=current_user.id,
        resource_id=access_request.resource_id,
        request_id=access_request.id,
        metadata={
            "denier_id": current_user.id,
            "requester_id": access_request.user_id,
            "denial_reason": deny_data.denial_reason,
        },
        is_break_glass=access_request.is_break_glass,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    requester = db.query(models.User).filter(models.User.id == access_request.user_id).first()
    background_tasks.add_task(
        slack_service.notify_request_denied,
        request_id=access_request.id,
        requester_name=requester.name if requester else "Unknown",
        denier_name=current_user.name,
        resource_name=resource_obj.name if resource_obj else "Unknown",
        denial_reason=deny_data.denial_reason,
    )
    
    return access_request
