"""
Demo protected endpoints that require JWT tokens
"""
from fastapi import APIRouter, Request
from typing import Dict, Any

router = APIRouter(prefix="/protected", tags=["Protected Resources"])


@router.get("/api/data")
def get_protected_data(request: Request) -> Dict[str, Any]:
    """
    Demo protected endpoint
    
    This endpoint requires a valid JWT token to access.
    It demonstrates how resources can be protected using the gateway middleware.
    """
    return {
        "message": "Access granted to protected resource",
        "user_id": request.state.user_id,
        "resource_id": request.state.resource_id,
        "scope": request.state.scope,
        "request_id": request.state.request_id,
        "data": {
            "example": "This is protected data",
            "timestamp": "2024-10-09T12:00:00Z",
            "records": [
                {"id": 1, "value": "Sample data 1"},
                {"id": 2, "value": "Sample data 2"},
                {"id": 3, "value": "Sample data 3"},
            ]
        }
    }


@router.get("/api/admin")
def get_admin_data(request: Request) -> Dict[str, Any]:
    """
    Demo admin-level protected endpoint
    """
    return {
        "message": "Access granted to admin resource",
        "user_id": request.state.user_id,
        "resource_id": request.state.resource_id,
        "scope": request.state.scope,
        "admin_data": {
            "system_status": "operational",
            "active_users": 42,
            "pending_requests": 7
        }
    }


@router.post("/api/action")
def perform_protected_action(request: Request, action_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Demo protected action endpoint
    """
    return {
        "message": "Action executed successfully",
        "user_id": request.state.user_id,
        "resource_id": request.state.resource_id,
        "action": action_data,
        "result": "success"
    }

