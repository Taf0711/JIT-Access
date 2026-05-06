"""
Demo Gateway Middleware for protecting resources with JWT validation
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from typing import Callable
import logging

from app.services.jwt_service import jwt_service
from app.db import SessionLocal
from app.services.audit import AuditService
from app.services.grants import validate_active_grant_for_token

logger = logging.getLogger(__name__)


def _get_session_factory(request: Request):
    return getattr(request.app.state, "gateway_session_factory", SessionLocal)


def _extract_required_resource_name(path: str) -> str | None:
    parts = path.strip("/").split("/")
    if len(parts) >= 3 and parts[0] == "protected" and parts[1] == "resources":
        return parts[2]
    return None


def _scope_allows_request(scope: str | None, method: str, path: str) -> bool:
    if scope == "admin":
        return True

    if method == "GET" and path.endswith("/data"):
        return scope in {"db:read", "api:access", "service:access", "read"}

    if method == "POST" and path.endswith("/action"):
        return scope in {"api:access", "service:access", "write"}

    return False


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
        db = _get_session_factory(request)()
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
    
    db = _get_session_factory(request)()
    try:
        grant, grant_error = validate_active_grant_for_token(
            db=db,
            token=token,
            payload=payload,
        )

        if grant_error:
            AuditService.log_event(
                db=db,
                event_type="GATEWAY_ACCESS_DENIED",
                user_id=int(payload.get("sub")),
                resource_id=payload.get("resource_id"),
                request_id=payload.get("request_id"),
                metadata={
                    "error": grant_error,
                    "path": request.url.path,
                    "method": request.method
                },
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": f"Access denied: {grant_error}",
                    "path": request.url.path
                }
            )

        required_resource_name = _extract_required_resource_name(request.url.path)
        token_resource_name = payload.get("resource_name")
        if not required_resource_name:
            denial_reason = "Protected route must include a resource name"
            AuditService.log_event(
                db=db,
                event_type="GATEWAY_ACCESS_DENIED",
                user_id=int(payload.get("sub")),
                resource_id=payload.get("resource_id"),
                request_id=payload.get("request_id"),
                metadata={
                    "error": denial_reason,
                    "path": request.url.path,
                    "method": request.method,
                    "scope": payload.get("scope"),
                    "resource_name": token_resource_name,
                },
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )

            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": f"Access denied: {denial_reason}",
                    "path": request.url.path,
                },
            )

        if token_resource_name != required_resource_name:
            denial_reason = "Token not valid for this resource"
            AuditService.log_event(
                db=db,
                event_type="GATEWAY_ACCESS_DENIED",
                user_id=int(payload.get("sub")),
                resource_id=payload.get("resource_id"),
                request_id=payload.get("request_id"),
                metadata={
                    "error": denial_reason,
                    "expected": required_resource_name,
                    "actual": token_resource_name,
                    "path": request.url.path,
                    "method": request.method,
                    "scope": payload.get("scope"),
                },
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": f"Access denied: {denial_reason}",
                    "path": request.url.path,
                },
            )

        if not _scope_allows_request(payload.get("scope"), request.method, request.url.path):
            denial_reason = "Token scope does not allow this action"
            AuditService.log_event(
                db=db,
                event_type="GATEWAY_ACCESS_DENIED",
                user_id=int(payload.get("sub")),
                resource_id=payload.get("resource_id"),
                request_id=payload.get("request_id"),
                metadata={
                    "error": denial_reason,
                    "path": request.url.path,
                    "method": request.method,
                    "scope": payload.get("scope"),
                    "resource_name": token_resource_name,
                },
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": f"Access denied: {denial_reason}",
                    "path": request.url.path,
                },
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
                "resource_name": token_resource_name
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        
    finally:
        db.close()
    
    # Add user context to request state
    request.state.user_id = int(payload.get("sub"))
    request.state.resource_id = payload.get("resource_id")
    request.state.resource_name = payload.get("resource_name")
    request.state.scope = payload.get("scope")
    request.state.request_id = payload.get("request_id")
    
    # Continue to protected endpoint
    response = await call_next(request)
    return response
