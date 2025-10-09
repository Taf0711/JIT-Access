"""
Tests for grants API endpoints
"""
import pytest
from datetime import datetime, timedelta
from app import models


def test_list_my_grants(client, sample_users, sample_resources, db_session):
    """Test listing user's active grants"""
    # Create an approved request
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test",
        status=models.RequestStatus.APPROVED,
        approved_by=sample_users[1].id
    )
    db_session.add(request)
    db_session.commit()
    
    # Create a grant
    grant = models.Grant(
        request_id=request.id,
        token_hash="test_hash_123",
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    db_session.add(grant)
    db_session.commit()
    
    response = client.get(
        "/api/v1/grants/me",
        headers={"X-API-Key": "test_requester_key"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["request_id"] == request.id


def test_list_grants_excludes_expired(client, sample_users, sample_resources, db_session):
    """Test that expired grants are excluded"""
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test",
        status=models.RequestStatus.APPROVED
    )
    db_session.add(request)
    db_session.commit()
    
    # Create an expired grant
    grant = models.Grant(
        request_id=request.id,
        token_hash="expired_hash",
        expires_at=datetime.utcnow() - timedelta(hours=1)  # Expired
    )
    db_session.add(grant)
    db_session.commit()
    
    response = client.get(
        "/api/v1/grants/me",
        headers={"X-API-Key": "test_requester_key"}
    )
    
    assert response.status_code == 200
    data = response.json()
    # Should not include expired grant
    assert len([g for g in data if g["id"] == grant.id]) == 0


def test_get_grant(client, sample_users, sample_resources, db_session):
    """Test getting a specific grant"""
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test",
        status=models.RequestStatus.APPROVED
    )
    db_session.add(request)
    db_session.commit()
    
    grant = models.Grant(
        request_id=request.id,
        token_hash="test_hash",
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    db_session.add(grant)
    db_session.commit()
    
    response = client.get(
        f"/api/v1/grants/{grant.id}",
        headers={"X-API-Key": "test_requester_key"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == grant.id


def test_revoke_grant(client, sample_users, sample_resources, db_session):
    """Test revoking a grant"""
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test",
        status=models.RequestStatus.APPROVED
    )
    db_session.add(request)
    db_session.commit()
    
    grant = models.Grant(
        request_id=request.id,
        token_hash="test_hash",
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    db_session.add(grant)
    db_session.commit()
    
    response = client.post(
        f"/api/v1/grants/{grant.id}/revoke",
        headers={"X-API-Key": "test_requester_key"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["revoked"] is True
    assert data["revoked_at"] is not None

