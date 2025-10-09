"""
Audit log endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import List, Optional
from datetime import datetime, timedelta
import csv
import io

from app.db import get_db
from app import models, schemas
from app.dependencies import get_current_user, require_role

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/events", response_model=List[schemas.AuditEvent])
def list_audit_events(
    event_type: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    resource_id: Optional[int] = Query(None),
    is_break_glass: Optional[bool] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(require_role(models.UserRole.ADMIN)),
):
    """
    List audit events with filtering
    
    Requires admin role. Supports filtering by:
    - event_type
    - user_id
    - resource_id
    - is_break_glass
    - date range (start_date, end_date)
    """
    
    query = db.query(models.AuditEvent)
    
    # Apply filters
    if event_type:
        query = query.filter(models.AuditEvent.event_type == event_type)
    
    if user_id is not None:
        query = query.filter(models.AuditEvent.user_id == user_id)
    
    if resource_id is not None:
        query = query.filter(models.AuditEvent.resource_id == resource_id)
    
    if is_break_glass is not None:
        query = query.filter(models.AuditEvent.is_break_glass == is_break_glass)
    
    if start_date:
        query = query.filter(models.AuditEvent.timestamp >= start_date)
    
    if end_date:
        query = query.filter(models.AuditEvent.timestamp <= end_date)
    
    # Order by most recent first
    query = query.order_by(models.AuditEvent.timestamp.desc())
    
    # Pagination
    events = query.offset(offset).limit(limit).all()
    
    return events


@router.get("/export")
def export_audit_events_csv(
    event_type: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    resource_id: Optional[int] = Query(None),
    is_break_glass: Optional[bool] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(require_role(models.UserRole.ADMIN)),
):
    """
    Export audit events to CSV
    
    Requires admin role. Returns a CSV file with all matching audit events.
    Supports same filtering options as list endpoint.
    """
    
    query = db.query(models.AuditEvent)
    
    # Apply same filters as list endpoint
    if event_type:
        query = query.filter(models.AuditEvent.event_type == event_type)
    
    if user_id is not None:
        query = query.filter(models.AuditEvent.user_id == user_id)
    
    if resource_id is not None:
        query = query.filter(models.AuditEvent.resource_id == resource_id)
    
    if is_break_glass is not None:
        query = query.filter(models.AuditEvent.is_break_glass == is_break_glass)
    
    if start_date:
        query = query.filter(models.AuditEvent.timestamp >= start_date)
    
    if end_date:
        query = query.filter(models.AuditEvent.timestamp <= end_date)
    
    # Order by timestamp
    query = query.order_by(models.AuditEvent.timestamp.asc())
    
    # Fetch all events (with reasonable limit)
    events = query.limit(10000).all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'id',
        'timestamp',
        'event_type',
        'user_id',
        'resource_id',
        'request_id',
        'is_break_glass',
        'ip_address',
        'user_agent',
        'metadata'
    ])
    
    # Write data rows
    for event in events:
        writer.writerow([
            event.id,
            event.timestamp.isoformat() if event.timestamp else '',
            event.event_type,
            event.user_id or '',
            event.resource_id or '',
            event.request_id or '',
            event.is_break_glass,
            event.ip_address or '',
            event.user_agent or '',
            str(event.event_metadata) if event.event_metadata else ''
        ])
    
    # Generate filename with timestamp
    filename = f"audit_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    
    # Return CSV as downloadable file
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/stats")
def get_audit_stats(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(require_role(models.UserRole.ADMIN)),
):
    """
    Get audit statistics for the specified number of days
    
    Returns aggregated metrics about audit events.
    """
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Total events
    total_events = db.query(func.count(models.AuditEvent.id)).filter(
        models.AuditEvent.timestamp >= start_date
    ).scalar()
    
    # Events by type
    events_by_type = db.query(
        models.AuditEvent.event_type,
        func.count(models.AuditEvent.id).label('count')
    ).filter(
        models.AuditEvent.timestamp >= start_date
    ).group_by(
        models.AuditEvent.event_type
    ).all()
    
    # Break-glass events
    break_glass_events = db.query(func.count(models.AuditEvent.id)).filter(
        models.AuditEvent.timestamp >= start_date,
        models.AuditEvent.is_break_glass == True
    ).scalar()
    
    # Events by user (top 10)
    events_by_user = db.query(
        models.AuditEvent.user_id,
        func.count(models.AuditEvent.id).label('count')
    ).filter(
        models.AuditEvent.timestamp >= start_date,
        models.AuditEvent.user_id.isnot(None)
    ).group_by(
        models.AuditEvent.user_id
    ).order_by(
        func.count(models.AuditEvent.id).desc()
    ).limit(10).all()
    
    # Events by resource (top 10)
    events_by_resource = db.query(
        models.AuditEvent.resource_id,
        func.count(models.AuditEvent.id).label('count')
    ).filter(
        models.AuditEvent.timestamp >= start_date,
        models.AuditEvent.resource_id.isnot(None)
    ).group_by(
        models.AuditEvent.resource_id
    ).order_by(
        func.count(models.AuditEvent.id).desc()
    ).limit(10).all()
    
    return {
        "period_days": days,
        "start_date": start_date.isoformat(),
        "total_events": total_events,
        "break_glass_events": break_glass_events,
        "events_by_type": {
            event_type: count for event_type, count in events_by_type
        },
        "top_users": [
            {"user_id": user_id, "event_count": count}
            for user_id, count in events_by_user
        ],
        "top_resources": [
            {"resource_id": resource_id, "event_count": count}
            for resource_id, count in events_by_resource
        ]
    }


@router.get("/retention")
def get_audit_retention_info(
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(require_role(models.UserRole.ADMIN)),
):
    """
    Get information about audit log retention
    
    Returns statistics about the audit log size and oldest/newest entries.
    """
    
    # Total audit events
    total_events = db.query(func.count(models.AuditEvent.id)).scalar()
    
    # Oldest and newest events
    oldest_event = db.query(models.AuditEvent).order_by(
        models.AuditEvent.timestamp.asc()
    ).first()
    
    newest_event = db.query(models.AuditEvent).order_by(
        models.AuditEvent.timestamp.desc()
    ).first()
    
    # Events by age buckets
    now = datetime.utcnow()
    
    last_24h = db.query(func.count(models.AuditEvent.id)).filter(
        models.AuditEvent.timestamp >= now - timedelta(hours=24)
    ).scalar()
    
    last_7d = db.query(func.count(models.AuditEvent.id)).filter(
        models.AuditEvent.timestamp >= now - timedelta(days=7)
    ).scalar()
    
    last_30d = db.query(func.count(models.AuditEvent.id)).filter(
        models.AuditEvent.timestamp >= now - timedelta(days=30)
    ).scalar()
    
    last_90d = db.query(func.count(models.AuditEvent.id)).filter(
        models.AuditEvent.timestamp >= now - timedelta(days=90)
    ).scalar()
    
    return {
        "total_events": total_events,
        "oldest_event": {
            "id": oldest_event.id,
            "timestamp": oldest_event.timestamp.isoformat(),
            "event_type": oldest_event.event_type
        } if oldest_event else None,
        "newest_event": {
            "id": newest_event.id,
            "timestamp": newest_event.timestamp.isoformat(),
            "event_type": newest_event.event_type
        } if newest_event else None,
        "events_by_age": {
            "last_24_hours": last_24h,
            "last_7_days": last_7d,
            "last_30_days": last_30d,
            "last_90_days": last_90d,
            "older_than_90_days": total_events - last_90d
        }
    }

