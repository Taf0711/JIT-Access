from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import models
from app.services.jwt_service import jwt_service


def validate_active_grant_for_token(
    db: Session,
    token: str,
    payload: dict[str, Any],
) -> tuple[Optional[models.Grant], Optional[str]]:
    """Validate that a JWT is backed by an active persisted grant."""
    token_hash = jwt_service.hash_token(token)
    grant = db.query(models.Grant).filter(models.Grant.token_hash == token_hash).first()

    if not grant:
        return None, "Token grant not found"

    if grant.revoked:
        return None, "Token has been revoked"

    if grant.expires_at <= datetime.utcnow():
        return None, "Token grant has expired"

    access_request = grant.access_request
    if not access_request:
        return None, "Token grant is not linked to an access request"

    if access_request.status != models.RequestStatus.APPROVED:
        return None, "Token grant is not linked to an approved request"

    if payload.get("request_id") != access_request.id:
        return None, "Token request does not match grant"

    if int(payload.get("sub")) != access_request.user_id:
        return None, "Token user does not match grant"

    if payload.get("resource_id") != access_request.resource_id:
        return None, "Token resource does not match grant"

    return grant, None
