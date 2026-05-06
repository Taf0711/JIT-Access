from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List
from datetime import datetime

from app.db import get_db
from app import models, schemas
from app.dependencies import get_current_user
from app.services.metrics import metrics_service

router = APIRouter(prefix="/grants", tags=["Grants"])


@router.get("/me", response_model=List[schemas.GrantDetail])
def list_my_grants(
    include_revoked: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(get_current_user),
):
    """List current user's active grants"""
    
    query = db.query(models.Grant).join(
        models.AccessRequest
    ).filter(
        models.AccessRequest.user_id == current_user.id
    )
    
    # Filter out expired and optionally revoked
    now = datetime.utcnow()
    if not include_revoked:
        query = query.filter(
            and_(
                models.Grant.expires_at > now,
                models.Grant.revoked == False
            )
        )
    else:
        query = query.filter(models.Grant.expires_at > now)
    
    grants = query.order_by(models.Grant.created_at.desc()).all()
    
    return grants


@router.get("/{grant_id}", response_model=schemas.GrantDetail)
def get_grant(
    grant_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(get_current_user),
):
    """Get a specific grant"""
    
    grant = db.query(models.Grant).filter(models.Grant.id == grant_id).first()
    if not grant:
        raise HTTPException(status_code=404, detail="Grant not found")
    
    # Check permissions - user can only view their own grants unless admin
    if current_user.role != models.UserRole.ADMIN:
        if grant.access_request.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to view this grant")
    
    return grant


@router.post("/{grant_id}/revoke", response_model=schemas.Grant)
def revoke_grant(
    grant_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(get_current_user),
):
    """Revoke a grant (only admin or grant owner)"""
    
    grant = db.query(models.Grant).filter(models.Grant.id == grant_id).first()
    if not grant:
        raise HTTPException(status_code=404, detail="Grant not found")
    
    # Check permissions
    if current_user.role != models.UserRole.ADMIN:
        if grant.access_request.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to revoke this grant")
    
    if grant.revoked:
        raise HTTPException(status_code=400, detail="Grant already revoked")
    
    # Revoke grant
    grant.revoked = True
    grant.revoked_at = datetime.utcnow()
    
    db.commit()
    db.refresh(grant)

    metrics_service.record_grant_revoked(
        "admin" if current_user.role == models.UserRole.ADMIN else "owner"
    )
    active_grants_count = db.query(models.Grant).filter(
        and_(
            models.Grant.expires_at > datetime.utcnow(),
            models.Grant.revoked == False,
        )
    ).count()
    metrics_service.update_active_grants_count(active_grants_count)
    
    return grant
