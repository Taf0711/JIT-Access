"""
JWT Token Service for issuing and validating access tokens
"""
import jwt
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class JWTService:
    """Service for JWT token generation and validation"""
    
    def __init__(self):
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
    
    def generate_token(
        self,
        user_id: int,
        resource_id: int,
        resource_name: str,
        scope: str,
        duration_seconds: int,
        request_id: int
    ) -> str:
        """
        Generate a JWT token for granted access
        
        Args:
            user_id: ID of the user
            resource_id: ID of the resource being accessed
            resource_name: Name of the resource
            scope: Access scope (e.g., 'read', 'write', 'admin')
            duration_seconds: Token validity duration
            request_id: ID of the access request
        
        Returns:
            str: JWT token
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=duration_seconds)
        
        payload = {
            "sub": str(user_id),  # Subject - user ID
            "resource_id": resource_id,
            "resource_name": resource_name,
            "scope": scope,
            "request_id": request_id,
            "iat": now,  # Issued at
            "exp": expires_at,  # Expiration
            "nbf": now,  # Not before
            "iss": "jit-access",  # Issuer
            "type": "access_token"
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    def validate_token(self, token: str) -> tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Validate a JWT token
        
        Returns:
            tuple: (is_valid: bool, payload: Optional[Dict], error: Optional[str])
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True
                }
            )
            
            # Additional validation
            if payload.get("type") != "access_token":
                return False, None, "Invalid token type"
            
            if payload.get("iss") != "jit-access":
                return False, None, "Invalid token issuer"
            
            return True, payload, None
            
        except jwt.ExpiredSignatureError:
            return False, None, "Token has expired"
        except jwt.InvalidTokenError as e:
            return False, None, f"Invalid token: {str(e)}"
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return False, None, f"Token validation failed: {str(e)}"
    
    def hash_token(self, token: str) -> str:
        """
        Generate SHA256 hash of token for storage
        
        Args:
            token: JWT token string
        
        Returns:
            str: Hex digest of SHA256 hash
        """
        return hashlib.sha256(token.encode()).hexdigest()
    
    def decode_without_validation(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode token without validation (for inspection only)
        
        Returns:
            Optional[Dict]: Decoded payload or None
        """
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception as e:
            logger.error(f"Token decode error: {e}")
            return None


# Singleton instance
jwt_service = JWTService()

