"""
Tests for access request API endpoints
"""
import pytest
from app import models


def test_create_access_request(client, sample_users, sample_resources, sample_policy):
    """Test creating an access request"""
    response = client.post(
        "/api/v1/requests",
        json={
            "resource_id": sample_resources[0].id,
            "duration_seconds": 3600,
            "justification": "Need to debug production issue in ticket #1234",
            "is_break_glass": False
        },
        headers={"X-API-Key": "test_requester_key"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["resource_id"] == sample_resources[0].id
    assert data["duration_seconds"] == 3600
    assert data["status"] == "pending"
    assert data["is_break_glass"] is False


def test_create_access_request_exceeds_max_ttl(client, sample_users, sample_resources, sample_policy):
    """Test that request exceeding max TTL is rejected"""
    response = client.post(
        "/api/v1/requests",
        json={
            "resource_id": sample_resources[0].id,
            "duration_seconds": 10000,  # Exceeds policy max_ttl_seconds of 7200
            "justification": "Testing max TTL validation",
            "is_break_glass": False
        },
        headers={"X-API-Key": "test_requester_key"}
    )
    
    assert response.status_code == 400
    assert "exceeds maximum TTL" in response.json()["detail"]


def test_create_break_glass_request_exceeds_emergency_ttl(client, sample_users, sample_resources):
    """Test that break-glass requests enforce emergency TTL policy."""
    response = client.post(
        "/api/v1/requests",
        json={
            "resource_id": sample_resources[0].id,
            "duration_seconds": 3600,
            "justification": "Emergency investigation for production incident",
            "is_break_glass": True
        },
        headers={"X-API-Key": "test_requester_key"}
    )

    assert response.status_code == 400
    assert "break-glass" in response.json()["detail"].lower()


def test_create_access_request_invalid_resource(client, sample_users):
    """Test creating request for non-existent resource"""
    response = client.post(
        "/api/v1/requests",
        json={
            "resource_id": 999,
            "duration_seconds": 3600,
            "justification": "Testing invalid resource",
            "is_break_glass": False
        },
        headers={"X-API-Key": "test_requester_key"}
    )
    
    assert response.status_code == 404


def test_create_access_request_no_auth(client, sample_resources):
    """Test creating request without authentication"""
    response = client.post(
        "/api/v1/requests",
        json={
            "resource_id": sample_resources[0].id,
            "duration_seconds": 3600,
            "justification": "Testing auth",
            "is_break_glass": False
        }
    )
    
    assert response.status_code == 401


def test_list_access_requests(client, sample_users, sample_resources, sample_policy, db_session):
    """Test listing access requests"""
    # Create a request
    request = models.AccessRequest(
        user_id=sample_users[2].id,  # Requester
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test request",
        status=models.RequestStatus.PENDING
    )
    db_session.add(request)
    db_session.commit()
    
    response = client.get(
        "/api/v1/requests",
        headers={"X-API-Key": "test_requester_key"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["status"] == "pending"


def test_approve_access_request(client, sample_users, sample_resources, db_session):
    """Test approving an access request"""
    # Create a pending request
    request = models.AccessRequest(
        user_id=sample_users[2].id,  # Requester
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test request for approval",
        status=models.RequestStatus.PENDING
    )
    db_session.add(request)
    db_session.commit()
    
    response = client.post(
        f"/api/v1/requests/{request.id}/approve",
        headers={"X-API-Key": "test_approver_key"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert data["approved_by"] == sample_users[1].id  # Approver


def test_break_glass_first_approval_stays_pending(client, sample_users, sample_resources, db_session):
    """Test that break-glass requests are not finalized by one approval."""
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=1800,
        justification="Urgent production incident",
        status=models.RequestStatus.PENDING,
        is_break_glass=True,
    )
    db_session.add(request)
    db_session.commit()

    response = client.post(
        f"/api/v1/requests/{request.id}/approve",
        headers={"X-API-Key": "test_approver_key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["approved_by"] is None

    approvals = db_session.query(models.AccessRequestApproval).filter(
        models.AccessRequestApproval.request_id == request.id
    ).all()
    assert len(approvals) == 1
    assert approvals[0].approver_id == sample_users[1].id

    token_response = client.post(
        "/api/v1/tokens/issue",
        json={"request_id": request.id},
        headers={"X-API-Key": "test_requester_key"},
    )
    assert token_response.status_code == 400


def test_break_glass_second_distinct_approval_finalizes(client, sample_users, sample_resources, db_session):
    """Test that break-glass approval requires two distinct approvers."""
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=1800,
        justification="Urgent production incident",
        status=models.RequestStatus.PENDING,
        is_break_glass=True,
    )
    db_session.add(request)
    db_session.commit()

    first_response = client.post(
        f"/api/v1/requests/{request.id}/approve",
        headers={"X-API-Key": "test_approver_key"},
    )
    assert first_response.status_code == 200

    second_response = client.post(
        f"/api/v1/requests/{request.id}/approve",
        headers={"X-API-Key": "test_admin_key"},
    )

    assert second_response.status_code == 200
    data = second_response.json()
    assert data["status"] == "approved"
    assert data["approved_by"] == sample_users[0].id

    approvals = db_session.query(models.AccessRequestApproval).filter(
        models.AccessRequestApproval.request_id == request.id
    ).all()
    assert len(approvals) == 2


def test_break_glass_duplicate_approver_rejected(client, sample_users, sample_resources, db_session):
    """Test that the same approver cannot count twice for break-glass."""
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=1800,
        justification="Urgent production incident",
        status=models.RequestStatus.PENDING,
        is_break_glass=True,
    )
    db_session.add(request)
    db_session.commit()

    first_response = client.post(
        f"/api/v1/requests/{request.id}/approve",
        headers={"X-API-Key": "test_approver_key"},
    )
    assert first_response.status_code == 200

    duplicate_response = client.post(
        f"/api/v1/requests/{request.id}/approve",
        headers={"X-API-Key": "test_approver_key"},
    )

    assert duplicate_response.status_code == 400
    assert "already approved" in duplicate_response.json()["detail"].lower()


def test_approve_own_request_rejected(client, sample_users, sample_resources, db_session):
    """Test that users cannot approve their own requests"""
    # Create a request as requester
    request = models.AccessRequest(
        user_id=sample_users[2].id,  # Requester
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test self-approval",
        status=models.RequestStatus.PENDING
    )
    db_session.add(request)
    db_session.commit()
    
    # Try to approve with same user (requester has id 2)
    response = client.post(
        f"/api/v1/requests/{request.id}/approve",
        headers={"X-API-Key": "test_requester_key"}
    )
    
    # Should fail because requesters can't approve
    assert response.status_code == 403


def test_deny_access_request(client, sample_users, sample_resources, db_session):
    """Test denying an access request"""
    # Create a pending request
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test request for denial",
        status=models.RequestStatus.PENDING
    )
    db_session.add(request)
    db_session.commit()
    
    response = client.post(
        f"/api/v1/requests/{request.id}/deny",
        json={"denial_reason": "Insufficient justification provided"},
        headers={"X-API-Key": "test_approver_key"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "denied"
    assert data["denial_reason"] == "Insufficient justification provided"


def test_get_specific_request(client, sample_users, sample_resources, db_session):
    """Test getting a specific access request"""
    request = models.AccessRequest(
        user_id=sample_users[2].id,
        resource_id=sample_resources[0].id,
        duration_seconds=3600,
        justification="Test request",
        status=models.RequestStatus.PENDING
    )
    db_session.add(request)
    db_session.commit()
    
    response = client.get(
        f"/api/v1/requests/{request.id}",
        headers={"X-API-Key": "test_requester_key"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == request.id
    assert "requester" in data
    assert "resource" in data
