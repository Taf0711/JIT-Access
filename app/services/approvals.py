from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.services.audit import AuditService


BREAK_GLASS_APPROVALS_REQUIRED = 2


def approve_access_request(
    db: Session,
    access_request: models.AccessRequest,
    current_user: schemas.CurrentUser,
    request,
) -> tuple[models.AccessRequest, int, int, bool]:
    """Record an approval and finalize the request once enough approvals exist."""
    if access_request.status != models.RequestStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Request is already {access_request.status.value}")

    if access_request.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot approve your own request")

    existing_approvals = db.query(models.AccessRequestApproval).filter(
        models.AccessRequestApproval.request_id == access_request.id
    ).all()

    if any(approval.approver_id == current_user.id for approval in existing_approvals):
        raise HTTPException(status_code=400, detail="You have already approved this request")

    approvals_required = BREAK_GLASS_APPROVALS_REQUIRED if access_request.is_break_glass else 1
    approval = models.AccessRequestApproval(
        request_id=access_request.id,
        approver_id=current_user.id,
    )
    db.add(approval)

    approvals_count = len(existing_approvals) + 1
    finalized = approvals_count >= approvals_required
    if finalized:
        access_request.status = models.RequestStatus.APPROVED
        access_request.approved_by = current_user.id
        access_request.approved_at = datetime.utcnow()

    db.commit()
    db.refresh(access_request)

    ip_address, user_agent = AuditService.extract_request_info(request)
    AuditService.log_event(
        db=db,
        event_type="REQUEST_APPROVED" if finalized else "REQUEST_APPROVAL_RECORDED",
        user_id=current_user.id,
        resource_id=access_request.resource_id,
        request_id=access_request.id,
        metadata={
            "approver_id": current_user.id,
            "requester_id": access_request.user_id,
            "approvals_count": approvals_count,
            "approvals_required": approvals_required,
            "finalized": finalized,
        },
        is_break_glass=access_request.is_break_glass,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return access_request, approvals_count, approvals_required, finalized
