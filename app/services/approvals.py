from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.services.audit import AuditService
from app.services.policy import policy_service


BREAK_GLASS_APPROVALS_REQUIRED = 2


async def approve_access_request(
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

    policy = db.query(models.Policy).filter(
        models.Policy.resource_id == access_request.resource_id
    ).first()
    approval_rules = policy.approval_rules if policy else {}
    policy_config = {
        "approval_rules": approval_rules or {},
    }
    existing_approver_ids = [approval.approver_id for approval in existing_approvals]
    allowed, violations = await policy_service.evaluate_approval_policy(
        approver_id=current_user.id,
        approver_role=current_user.role.value,
        requester_id=access_request.user_id,
        resource_id=access_request.resource_id,
        is_break_glass=access_request.is_break_glass,
        policy_config=policy_config,
        existing_approvals=existing_approver_ids,
    )
    if not allowed:
        raise HTTPException(
            status_code=400,
            detail="; ".join(violations) if violations else "Approval denied by policy",
        )

    min_policy_approvers = int((approval_rules or {}).get("min_approvers", 1))
    approvals_required = max(
        min_policy_approvers,
        BREAK_GLASS_APPROVALS_REQUIRED if access_request.is_break_glass else 1,
    )
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
