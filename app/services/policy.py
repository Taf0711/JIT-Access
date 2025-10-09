"""
OPA Policy Service for evaluating access control policies
"""
import httpx
from typing import Dict, Any, List, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class PolicyService:
    """Service for interacting with OPA policy engine"""
    
    def __init__(self, opa_url: str = None):
        self.opa_url = opa_url or settings.OPA_URL
        self.client = httpx.Client(timeout=5.0)
    
    async def evaluate_request_policy(
        self,
        user_id: int,
        user_role: str,
        resource_id: int,
        resource_type: str,
        duration_seconds: int,
        is_break_glass: bool,
        resource_metadata: Dict[str, Any],
        policy_config: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """
        Evaluate if an access request is allowed by policy
        
        Returns:
            tuple: (allowed: bool, violations: List[str])
        """
        input_data = {
            "request": {
                "user_id": user_id,
                "user_role": user_role,
                "resource_id": resource_id,
                "resource_type": resource_type,
                "duration_seconds": duration_seconds,
                "is_break_glass": is_break_glass,
                "resource_metadata": resource_metadata
            },
            "policy": {
                "max_ttl_seconds": policy_config.get("max_ttl_seconds", 86400),
                "approval_rules": policy_config.get("approval_rules", {}),
                "time_window_restrictions": policy_config.get("time_window_restrictions", {})
            }
        }
        
        try:
            response = self.client.post(
                f"{self.opa_url}/v1/data/jit/access/allow_request",
                json={"input": input_data}
            )
            response.raise_for_status()
            result = response.json()
            allowed = result.get("result", False)
            
            # Get violations if any
            violations = []
            if not allowed:
                violation_response = self.client.post(
                    f"{self.opa_url}/v1/data/jit/access/violation",
                    json={"input": input_data}
                )
                if violation_response.status_code == 200:
                    violation_result = violation_response.json()
                    violations = violation_result.get("result", [])
            
            return allowed, violations
            
        except httpx.HTTPError as e:
            logger.error(f"OPA policy evaluation failed: {e}")
            # Fail closed - deny by default
            return False, [f"Policy evaluation error: {str(e)}"]
    
    async def evaluate_approval_policy(
        self,
        approver_id: int,
        approver_role: str,
        requester_id: int,
        resource_id: int,
        is_break_glass: bool,
        policy_config: Dict[str, Any],
        existing_approvals: List[int]
    ) -> tuple[bool, List[str]]:
        """
        Evaluate if an approval is allowed by policy
        
        Returns:
            tuple: (allowed: bool, violations: List[str])
        """
        input_data = {
            "approver": {
                "user_id": approver_id,
                "role": approver_role
            },
            "request": {
                "requester_id": requester_id,
                "is_break_glass": is_break_glass,
                "resource_id": resource_id
            },
            "policy": {
                "approval_rules": policy_config.get("approval_rules", {
                    "min_approvers": 1,
                    "allowed_roles": ["approver", "admin"]
                })
            },
            "existing_approvals": existing_approvals
        }
        
        try:
            response = self.client.post(
                f"{self.opa_url}/v1/data/jit/access/allow_approval",
                json={"input": input_data}
            )
            response.raise_for_status()
            result = response.json()
            allowed = result.get("result", False)
            
            # Get violations if any
            violations = []
            if not allowed:
                violation_response = self.client.post(
                    f"{self.opa_url}/v1/data/jit/access/violation",
                    json={"input": input_data}
                )
                if violation_response.status_code == 200:
                    violation_result = violation_response.json()
                    violations = violation_result.get("result", [])
            
            return allowed, violations
            
        except httpx.HTTPError as e:
            logger.error(f"OPA approval policy evaluation failed: {e}")
            # Fail closed - deny by default
            return False, [f"Policy evaluation error: {str(e)}"]
    
    def health_check(self) -> bool:
        """Check if OPA is healthy"""
        try:
            response = self.client.get(f"{self.opa_url}/health")
            return response.status_code == 200
        except:
            return False
    
    def __del__(self):
        """Cleanup HTTP client"""
        self.client.close()


# Singleton instance
policy_service = PolicyService()

