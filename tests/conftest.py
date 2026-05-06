"""
Pytest configuration and fixtures for testing
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db import Base, get_db
from app.main import app
from app import models

# Use in-memory SQLite for tests
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    app.state.gateway_session_factory = TestingSessionLocal
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    del app.state.gateway_session_factory


@pytest.fixture(scope="function")
def sample_users(db_session):
    """Create sample users for testing"""
    users = [
        models.User(
            email="admin@test.com",
            name="Admin User",
            role=models.UserRole.ADMIN,
            api_key="test_admin_key"
        ),
        models.User(
            email="approver@test.com",
            name="Approver User",
            role=models.UserRole.APPROVER,
            api_key="test_approver_key"
        ),
        models.User(
            email="requester@test.com",
            name="Requester User",
            role=models.UserRole.REQUESTER,
            api_key="test_requester_key"
        ),
    ]
    for user in users:
        db_session.add(user)
    db_session.commit()
    return users


@pytest.fixture(scope="function")
def sample_resources(db_session):
    """Create sample resources for testing"""
    resources = [
        models.Resource(
            name="test-db",
            type=models.ResourceType.DATABASE,
            description="Test database",
            resource_metadata={"environment": "test"}
        ),
        models.Resource(
            name="test-api",
            type=models.ResourceType.API,
            description="Test API",
            resource_metadata={"environment": "test"}
        ),
    ]
    for resource in resources:
        db_session.add(resource)
    db_session.commit()
    return resources


@pytest.fixture(scope="function")
def sample_policy(db_session, sample_resources):
    """Create a sample policy"""
    policy = models.Policy(
        resource_id=sample_resources[0].id,
        name="Test Policy",
        max_ttl_seconds=7200,
        approval_rules={"min_approvers": 1},
        time_window_restrictions={}
    )
    db_session.add(policy)
    db_session.commit()
    return policy
