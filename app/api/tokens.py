"""
Token issuance endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request as FastAPIRequest
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional

from app.db import get_db
from app import models, schemas
from app.dependencies import get_current_user
from app.services.jwt_service import jwt_service
from app.services.audit import AuditService
from app.services.grants import validate_active_grant_for_token

router = APIRouter(prefix="/tokens", tags=["Tokens"])


class TokenIssueRequest(BaseModel):
    """Request to issue a token for an approved access request"""
    request_id: int


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "Bearer"
    expires_at: datetime
    scope: str
    resource_name: str


@router.post("/issue", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def issue_token(
    token_request: TokenIssueRequest,
    request: FastAPIRequest,
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(get_current_user),
):
    """
    Issue a JWT token for an approved access request
    
    This endpoint is called after a request has been approved to generate
    the actual short-lived access token.
    """
    
    # Get the access request
    access_request = db.query(models.AccessRequest).filter(
        models.AccessRequest.id == token_request.request_id
    ).first()
    
    if not access_request:
        raise HTTPException(status_code=404, detail="Access request not found")
    
    # Verify request belongs to current user
    if access_request.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to issue token for this request"
        )
    
    # Verify request is approved
    if access_request.status != models.RequestStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot issue token for {access_request.status.value} request"
        )
    
    # Check if grant already exists
    existing_grant = db.query(models.Grant).filter(
        models.Grant.request_id == access_request.id
    ).first()
    
    if existing_grant:
        raise HTTPException(
            status_code=400,
            detail="Token already issued for this request; create a new access request for replacement access"
        )
    
    # Get resource info
    resource = db.query(models.Resource).filter(
        models.Resource.id == access_request.resource_id
    ).first()
    
    # Determine scope based on resource type
    scope = "read"
    if resource.type == models.ResourceType.DATABASE:
        scope = "db:read"
    elif resource.type == models.ResourceType.API:
        scope = "api:access"
    elif resource.type == models.ResourceType.SERVICE:
        scope = "service:access"
    
    # Generate JWT token
    token = jwt_service.generate_token(
        user_id=current_user.id,
        resource_id=resource.id,
        resource_name=resource.name,
        scope=scope,
        duration_seconds=access_request.duration_seconds,
        request_id=access_request.id
    )
    
    # Calculate expiration
    expires_at = datetime.utcnow() + timedelta(seconds=access_request.duration_seconds)
    
    # Store grant
    grant = models.Grant(
        request_id=access_request.id,
        token_hash=jwt_service.hash_token(token),
        expires_at=expires_at,
        revoked=False
    )
    db.add(grant)
    db.commit()
    db.refresh(grant)
    
    # Audit log
    ip_address, user_agent = AuditService.extract_request_info(request)
    AuditService.log_event(
        db=db,
        event_type="TOKEN_ISSUED",
        user_id=current_user.id,
        resource_id=resource.id,
        request_id=access_request.id,
        metadata={
            "grant_id": grant.id,
            "expires_at": expires_at.isoformat(),
            "scope": scope
        },
        is_break_glass=access_request.is_break_glass,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    return TokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_at=expires_at,
        scope=scope,
        resource_name=resource.name
    )


class TokenValidateRequest(BaseModel):
    """Request to validate a token"""
    token: str
    resource_name: Optional[str] = None


class TokenValidateResponse(BaseModel):
    """Token validation response"""
    valid: bool
    user_id: Optional[int] = None
    resource_id: Optional[int] = None
    resource_name: Optional[str] = None
    scope: Optional[str] = None
    expires_at: Optional[datetime] = None
    error: Optional[str] = None


@router.post("/validate", response_model=TokenValidateResponse)
async def validate_token(
    validate_request: TokenValidateRequest,
    request: FastAPIRequest,
    db: Session = Depends(get_db),
):
    """
    Validate a JWT token
    
    This endpoint is used by protected services to validate access tokens.
    """
    
    # Validate JWT
    is_valid, payload, error = jwt_service.validate_token(validate_request.token)
    
    if not is_valid or not payload:
        # Audit failed validation
        AuditService.log_event(
            db=db,
            event_type="TOKEN_VALIDATION_FAILED",
            metadata={"error": error, "resource_name": validate_request.resource_name},
            ip_address=request.client.host if request.client else None,
        )
        
        return TokenValidateResponse(
            valid=False,
            error=error
        )
    
    grant, grant_error = validate_active_grant_for_token(
        db=db,
        token=validate_request.token,
        payload=payload,
    )

    if grant_error:
        AuditService.log_event(
            db=db,
            event_type="TOKEN_VALIDATION_FAILED",
            user_id=int(payload.get("sub")),
            resource_id=payload.get("resource_id"),
            request_id=payload.get("request_id"),
            metadata={"error": grant_error},
            ip_address=request.client.host if request.client else None,
        )
        
        return TokenValidateResponse(
            valid=False,
            error=grant_error
        )
    
    # Check resource name if provided
    if validate_request.resource_name:
        if payload.get("resource_name") != validate_request.resource_name:
            AuditService.log_event(
                db=db,
                event_type="TOKEN_VALIDATION_FAILED",
                user_id=int(payload.get("sub")),
                resource_id=payload.get("resource_id"),
                metadata={
                    "error": "Resource mismatch",
                    "expected": validate_request.resource_name,
                    "actual": payload.get("resource_name")
                },
                ip_address=request.client.host if request.client else None,
            )
            
            return TokenValidateResponse(
                valid=False,
                error="Token not valid for this resource"
            )
    
    # Audit successful validation
    AuditService.log_event(
        db=db,
        event_type="TOKEN_VALIDATED",
        user_id=int(payload.get("sub")),
        resource_id=payload.get("resource_id"),
        request_id=payload.get("request_id"),
        metadata={
            "scope": payload.get("scope"),
            "resource_name": payload.get("resource_name")
        },
        ip_address=request.client.host if request.client else None,
    )
    
    return TokenValidateResponse(
        valid=True,
        user_id=int(payload.get("sub")),
        resource_id=payload.get("resource_id"),
        resource_name=payload.get("resource_name"),
        scope=payload.get("scope"),
        expires_at=datetime.fromtimestamp(payload.get("exp"))
    )
