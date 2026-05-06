"""
Tests for token issuance and validation
"""
import pytest
from datetime import datetime, timedelta
from app import models
from app.services.jwt_service import jwt_service


def test_issue_token_for_approved_request(client, sample_users, sample_resources, db_session):
    """Test issuing a token for an approved request"""
    # Create an approved request
    request = models.AccessRequest(
        user_id=sample_users[2].id,  # Requester
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test request",
        status=models.RequestStatus.APPROVED,
        approved_by=sample_users[1].id,
        approved_at=datetime.utcnow()
    )
    db_session.add(request)
    db_session.commit()
    
    response = client.post(
        "/api/v1/tokens/issue",
        json={"request_id": request.id},
        headers={"X-API-Key": "test_requester_key"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "Bearer"
    assert "expires_at" in data
    assert data["resource_name"] == sample_resources[0].name


def test_issue_token_for_pending_request_fails(client, sample_users, sample_resources, db_session):
    """Test that token issuance fails for pending requests"""
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test request",
        status=models.RequestStatus.PENDING
    )
    db_session.add(request)
    db_session.commit()
    
    response = client.post(
        "/api/v1/tokens/issue",
        json={"request_id": request.id},
        headers={"X-API-Key": "test_requester_key"}
    )
    
    assert response.status_code == 400
    assert "pending" in response.json()["detail"].lower()


def test_issue_token_for_other_users_request_fails(client, sample_users, sample_resources, db_session):
    """Test that users cannot issue tokens for other users' requests"""
    request = models.AccessRequest(
        user_id=sample_users[1].id,  # Different user
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test request",
        status=models.RequestStatus.APPROVED,
        approved_by=sample_users[0].id
    )
    db_session.add(request)
    db_session.commit()
    
    response = client.post(
        "/api/v1/tokens/issue",
        json={"request_id": request.id},
        headers={"X-API-Key": "test_requester_key"}  # Requester trying to issue for approver's request
    )
    
    assert response.status_code == 403


def test_issue_token_after_revocation_requires_new_request(client, sample_users, sample_resources, db_session):
    """Test that a revoked grant does not allow reissuing for the same request."""
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test request",
        status=models.RequestStatus.APPROVED,
        approved_by=sample_users[1].id
    )
    db_session.add(request)
    db_session.commit()

    first_response = client.post(
        "/api/v1/tokens/issue",
        json={"request_id": request.id},
        headers={"X-API-Key": "test_requester_key"}
    )
    assert first_response.status_code == 201

    grant = db_session.query(models.Grant).filter(
        models.Grant.request_id == request.id
    ).first()
    grant.revoked = True
    grant.revoked_at = datetime.utcnow()
    db_session.commit()

    second_response = client.post(
        "/api/v1/tokens/issue",
        json={"request_id": request.id},
        headers={"X-API-Key": "test_requester_key"}
    )

    assert second_response.status_code == 400
    assert "new access request" in second_response.json()["detail"].lower()


def test_validate_valid_token(client, sample_users, sample_resources, db_session):
    """Test validating a valid token"""
    # Create approved request
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test request",
        status=models.RequestStatus.APPROVED,
        approved_by=sample_users[1].id
    )
    db_session.add(request)
    db_session.commit()
    
    # Issue token
    issue_response = client.post(
        "/api/v1/tokens/issue",
        json={"request_id": request.id},
        headers={"X-API-Key": "test_requester_key"}
    )
    token = issue_response.json()["access_token"]
    
    # Validate token
    validate_response = client.post(
        "/api/v1/tokens/validate",
        json={"token": token, "resource_name": sample_resources[0].name}
    )
    
    assert validate_response.status_code == 200
    data = validate_response.json()
    assert data["valid"] is True
    assert data["user_id"] == sample_users[2].id
    assert data["resource_name"] == sample_resources[0].name


def test_validate_invalid_token(client):
    """Test validating an invalid token"""
    response = client.post(
        "/api/v1/tokens/validate",
        json={"token": "invalid_token_123"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["error"] is not None


def test_validate_revoked_token(client, sample_users, sample_resources, db_session):
    """Test that revoked tokens fail validation"""
    # Create and approve request
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test request",
        status=models.RequestStatus.APPROVED,
        approved_by=sample_users[1].id
    )
    db_session.add(request)
    db_session.commit()
    
    # Issue token
    issue_response = client.post(
        "/api/v1/tokens/issue",
        json={"request_id": request.id},
        headers={"X-API-Key": "test_requester_key"}
    )
    token = issue_response.json()["access_token"]
    
    # Revoke the grant
    grant = db_session.query(models.Grant).filter(
        models.Grant.request_id == request.id
    ).first()
    grant.revoked = True
    grant.revoked_at = datetime.utcnow()
    db_session.commit()
    
    # Try to validate revoked token
    validate_response = client.post(
        "/api/v1/tokens/validate",
        json={"token": token}
    )
    
    assert validate_response.status_code == 200
    data = validate_response.json()
    assert data["valid"] is False
    assert "revoked" in data["error"].lower()


def test_validate_signed_token_without_grant_fails(client, sample_users, sample_resources):
    """Test that a signed JWT is invalid without a persisted grant."""
    token = jwt_service.generate_token(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        resource_name=sample_resources[0].name,
        scope="db:read",
        duration_seconds=3600,
        request_id=12345,
    )

    response = client.post(
        "/api/v1/tokens/validate",
        json={"token": token},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert "grant not found" in data["error"].lower()


def test_validate_expired_grant_fails(client, sample_users, sample_resources, db_session):
    """Test that a valid JWT is rejected when its grant is expired."""
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test request",
        status=models.RequestStatus.APPROVED,
        approved_by=sample_users[1].id,
    )
    db_session.add(request)
    db_session.commit()

    issue_response = client.post(
        "/api/v1/tokens/issue",
        json={"request_id": request.id},
        headers={"X-API-Key": "test_requester_key"},
    )
    token = issue_response.json()["access_token"]

    grant = db_session.query(models.Grant).filter(
        models.Grant.request_id == request.id
    ).first()
    grant.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()

    response = client.post(
        "/api/v1/tokens/validate",
        json={"token": token},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert "expired" in data["error"].lower()


def test_protected_endpoint_with_valid_token(client, sample_users, sample_resources, db_session):
    """Test accessing protected endpoint with valid token"""
    # Create and approve request
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test request",
        status=models.RequestStatus.APPROVED,
        approved_by=sample_users[1].id
    )
    db_session.add(request)
    db_session.commit()
    
    # Issue token
    issue_response = client.post(
        "/api/v1/tokens/issue",
        json={"request_id": request.id},
        headers={"X-API-Key": "test_requester_key"}
    )
    token = issue_response.json()["access_token"]
    
    # Access protected endpoint
    response = client.get(
        f"/protected/resources/{sample_resources[0].name}/data",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["user_id"] == sample_users[2].id
    assert data["resource_name"] == sample_resources[0].name


def test_protected_endpoint_rejects_wrong_resource_token(client, sample_users, sample_resources, db_session):
    """Test that gateway access is bound to the token resource."""
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test request",
        status=models.RequestStatus.APPROVED,
        approved_by=sample_users[1].id
    )
    db_session.add(request)
    db_session.commit()

    issue_response = client.post(
        "/api/v1/tokens/issue",
        json={"request_id": request.id},
        headers={"X-API-Key": "test_requester_key"}
    )
    token = issue_response.json()["access_token"]

    response = client.get(
        f"/protected/resources/{sample_resources[1].name}/data",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert "resource" in response.json()["detail"].lower()


def test_protected_endpoint_rejects_disallowed_scope(client, sample_users, sample_resources, db_session):
    """Test that read-only database tokens cannot perform protected actions."""
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test request",
        status=models.RequestStatus.APPROVED,
        approved_by=sample_users[1].id
    )
    db_session.add(request)
    db_session.commit()

    issue_response = client.post(
        "/api/v1/tokens/issue",
        json={"request_id": request.id},
        headers={"X-API-Key": "test_requester_key"}
    )
    token = issue_response.json()["access_token"]

    response = client.post(
        f"/protected/resources/{sample_resources[0].name}/action",
        json={"operation": "restart"},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert "scope" in response.json()["detail"].lower()


def test_protected_action_accepts_action_scope(client, sample_users, sample_resources, db_session):
    """Test that API access tokens can perform protected actions."""
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[1].id,
        duration_seconds=3600,
        justification="Test request",
        status=models.RequestStatus.APPROVED,
        approved_by=sample_users[1].id
    )
    db_session.add(request)
    db_session.commit()

    issue_response = client.post(
        "/api/v1/tokens/issue",
        json={"request_id": request.id},
        headers={"X-API-Key": "test_requester_key"}
    )
    token = issue_response.json()["access_token"]

    response = client.post(
        f"/protected/resources/{sample_resources[1].name}/action",
        json={"operation": "refresh"},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["resource_name"] == sample_resources[1].name


def test_protected_endpoint_without_token_fails(client):
    """Test that protected endpoint requires token"""
    response = client.get("/protected/resources/test-db/data")
    
    assert response.status_code == 401
    assert "Authorization" in response.json()["detail"]


def test_protected_endpoint_with_invalid_token_fails(client):
    """Test that protected endpoint rejects invalid tokens"""
    response = client.get(
        "/protected/resources/test-db/data",
        headers={"Authorization": "Bearer invalid_token"}
    )
    
    assert response.status_code == 403
