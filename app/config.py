from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://jituser:jitpass@localhost:5432/jitaccess"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT
    JWT_SECRET_KEY: str = "dev-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_PRIVATE_KEY_PATH: Optional[str] = None
    JWT_PUBLIC_KEY_PATH: Optional[str] = None
    
    # OPA
    OPA_URL: str = "http://localhost:8181"
    POLICY_ENGINE: str = "local"
    
    # Slack
    SLACK_WEBHOOK_URL: Optional[str] = None
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

