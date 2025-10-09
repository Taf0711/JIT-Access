from fastapi import Header, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import Optional
from app.db import get_db
from app import models, schemas


async def get_current_user(
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> schemas.CurrentUser:
    """
    Extract current user from API key header.
    This is a simple auth stub - in production, use OAuth2/OIDC.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    user = db.query(models.User).filter(models.User.api_key == x_api_key).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return schemas.CurrentUser.model_validate(user)


def require_role(required_role: models.UserRole):
    """Dependency factory to require specific role"""
    def role_checker(current_user: schemas.CurrentUser = Depends(get_current_user)):
        if current_user.role != required_role and current_user.role != models.UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {required_role.value}"
            )
        return current_user
    return role_checker

