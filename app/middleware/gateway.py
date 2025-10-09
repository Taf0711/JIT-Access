"""
Demo Gateway Middleware for protecting resources with JWT validation
"""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Callable
import logging

from app.services.jwt_service import jwt_service
from app.db import SessionLocal
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


async def gateway_auth_middleware(request: Request, call_next: Callable):
    """
    Middleware to protect /protected/* endpoints with JWT validation
    
    This is a demo gateway showing how to enforce JIT access tokens
    on protected resources.
    """
    
    # Only apply to /protected/* paths
    if not request.url.path.startswith("/protected/"):
        return await call_next(request)
    
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "detail": "Missing or invalid Authorization header",
                "required_format": "Authorization: Bearer <token>"
            }
        )
    
    token = auth_header.replace("Bearer ", "")
    
    # Validate token
    is_valid, payload, error = jwt_service.validate_token(token)
    
    if not is_valid or not payload:
        # Audit failed access attempt
        db = SessionLocal()
        try:
            AuditService.log_event(
                db=db,
                event_type="GATEWAY_ACCESS_DENIED",
                metadata={
                    "error": error,
                    "path": request.url.path,
                    "method": request.method
                },
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        finally:
            db.close()
        
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": f"Access denied: {error}",
                "path": request.url.path
            }
        )
    
    # Check if token is revoked
    token_hash = jwt_service.hash_token(token)
    db = SessionLocal()
    try:
        from app.models import Grant
        grant = db.query(Grant).filter(Grant.token_hash == token_hash).first()
        
        if grant and grant.revoked:
            AuditService.log_event(
                db=db,
                event_type="GATEWAY_ACCESS_DENIED",
                user_id=int(payload.get("sub")),
                resource_id=payload.get("resource_id"),
                request_id=payload.get("request_id"),
                metadata={
                    "error": "Token revoked",
                    "path": request.url.path,
                    "method": request.method
                },
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": "Access denied: Token has been revoked",
                    "path": request.url.path
                }
            )
        
        # Successful access - audit log
        AuditService.log_event(
            db=db,
            event_type="GATEWAY_ACCESS_GRANTED",
            user_id=int(payload.get("sub")),
            resource_id=payload.get("resource_id"),
            request_id=payload.get("request_id"),
            metadata={
                "path": request.url.path,
                "method": request.method,
                "scope": payload.get("scope"),
                "resource_name": payload.get("resource_name")
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        
    finally:
        db.close()
    
    # Add user context to request state
    request.state.user_id = int(payload.get("sub"))
    request.state.resource_id = payload.get("resource_id")
    request.state.scope = payload.get("scope")
    request.state.request_id = payload.get("request_id")
    
    # Continue to protected endpoint
    response = await call_next(request)
    return response

