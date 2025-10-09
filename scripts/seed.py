"""
Seed script to populate database with sample data for testing
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets

from app.db import SessionLocal, engine, Base
from app import models


def generate_api_key():
    """Generate a random API key"""
    return f"jit_{secrets.token_urlsafe(32)}"


def seed_database():
    """Seed the database with sample data"""
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Check if data already exists
        existing_users = db.query(models.User).count()
        if existing_users > 0:
            print("Database already seeded. Skipping...")
            return
        
        print("Seeding database...")
        
        # Create users
        users = [
            models.User(
                email="admin@example.com",
                name="Admin User",
                role=models.UserRole.ADMIN,
                api_key=generate_api_key()
            ),
            models.User(
                email="approver1@example.com",
                name="Alice Approver",
                role=models.UserRole.APPROVER,
                api_key=generate_api_key()
            ),
            models.User(
                email="approver2@example.com",
                name="Bob Approver",
                role=models.UserRole.APPROVER,
                api_key=generate_api_key()
            ),
            models.User(
                email="requester1@example.com",
                name="Charlie Requester",
                role=models.UserRole.REQUESTER,
                api_key=generate_api_key()
            ),
            models.User(
                email="requester2@example.com",
                name="Diana Requester",
                role=models.UserRole.REQUESTER,
                api_key=generate_api_key()
            ),
        ]
        
        for user in users:
            db.add(user)
            print(f"Created user: {user.email} (API Key: {user.api_key})")
        
        db.commit()
        
        # Create resources
        resources = [
            models.Resource(
                name="prod-orders-db",
                type=models.ResourceType.DATABASE,
                description="Production orders database (read-only access)",
                resource_metadata={"environment": "production", "tier": "critical"}
            ),
            models.Resource(
                name="prod-users-db",
                type=models.ResourceType.DATABASE,
                description="Production users database (read-only access)",
                resource_metadata={"environment": "production", "tier": "critical", "pii": True}
            ),
            models.Resource(
                name="staging-api",
                type=models.ResourceType.API,
                description="Staging API server access",
                resource_metadata={"environment": "staging", "tier": "medium"}
            ),
            models.Resource(
                name="prod-api",
                type=models.ResourceType.API,
                description="Production API server access",
                resource_metadata={"environment": "production", "tier": "critical"}
            ),
            models.Resource(
                name="prod-cache-redis",
                type=models.ResourceType.SERVICE,
                description="Production Redis cache access",
                resource_metadata={"environment": "production", "tier": "high"}
            ),
            models.Resource(
                name="staging-db",
                type=models.ResourceType.DATABASE,
                description="Staging database full access",
                resource_metadata={"environment": "staging", "tier": "low"}
            ),
            models.Resource(
                name="prod-monitoring",
                type=models.ResourceType.SERVICE,
                description="Production monitoring dashboards",
                resource_metadata={"environment": "production", "tier": "medium"}
            ),
            models.Resource(
                name="prod-logs",
                type=models.ResourceType.SERVICE,
                description="Production log aggregation system",
                resource_metadata={"environment": "production", "tier": "high"}
            ),
            models.Resource(
                name="dev-environment",
                type=models.ResourceType.SERVER,
                description="Development environment SSH access",
                resource_metadata={"environment": "development", "tier": "low"}
            ),
            models.Resource(
                name="prod-payment-service",
                type=models.ResourceType.SERVICE,
                description="Production payment processing service",
                resource_metadata={"environment": "production", "tier": "critical", "pci": True}
            ),
        ]
        
        for resource in resources:
            db.add(resource)
            print(f"Created resource: {resource.name}")
        
        db.commit()
        
        # Create policies
        policies = [
            models.Policy(
                resource_id=1,  # prod-orders-db
                name="Production DB Standard Access",
                max_ttl_seconds=7200,  # 2 hours
                approval_rules={"min_approvers": 1, "allowed_roles": ["approver", "admin"]},
                time_window_restrictions={"no_access_days": []}
            ),
            models.Policy(
                resource_id=2,  # prod-users-db (PII data)
                name="PII Data Access Policy",
                max_ttl_seconds=3600,  # 1 hour
                approval_rules={"min_approvers": 1, "allowed_roles": ["approver", "admin"], "requires_justification": True},
                time_window_restrictions={"no_access_days": [], "business_hours_only": True}
            ),
            models.Policy(
                resource_id=4,  # prod-api
                name="Production API Access",
                max_ttl_seconds=14400,  # 4 hours
                approval_rules={"min_approvers": 1},
                time_window_restrictions={"no_access_days": []}
            ),
            models.Policy(
                resource_id=6,  # staging-db
                name="Staging DB Liberal Access",
                max_ttl_seconds=28800,  # 8 hours
                approval_rules={"min_approvers": 1},
                time_window_restrictions={}
            ),
            models.Policy(
                resource_id=10,  # prod-payment-service
                name="Payment Service Restricted Access",
                max_ttl_seconds=1800,  # 30 minutes
                approval_rules={"min_approvers": 2, "allowed_roles": ["admin"]},
                time_window_restrictions={"no_access_days": [5, 6], "business_hours_only": True}  # No weekend access
            ),
        ]
        
        for policy in policies:
            db.add(policy)
            print(f"Created policy: {policy.name}")
        
        db.commit()
        
        # Create some historical access requests for demo
        access_requests = [
            models.AccessRequest(
                user_id=4,  # Charlie Requester
                resource_id=1,  # prod-orders-db
                duration_seconds=3600,
                justification="Need to investigate customer order discrepancy reported in ticket #1234",
                status=models.RequestStatus.APPROVED,
                approved_by=2,  # Alice Approver
                approved_at=datetime.utcnow() - timedelta(hours=2),
                is_break_glass=False,
                created_at=datetime.utcnow() - timedelta(hours=3)
            ),
            models.AccessRequest(
                user_id=5,  # Diana Requester
                resource_id=3,  # staging-api
                duration_seconds=7200,
                justification="Testing new feature deployment in staging environment",
                status=models.RequestStatus.APPROVED,
                approved_by=2,  # Alice Approver
                approved_at=datetime.utcnow() - timedelta(hours=1),
                is_break_glass=False,
                created_at=datetime.utcnow() - timedelta(hours=2)
            ),
            models.AccessRequest(
                user_id=4,  # Charlie Requester
                resource_id=2,  # prod-users-db (PII)
                duration_seconds=1800,
                justification="Debug user authentication issue - urgent production incident",
                status=models.RequestStatus.DENIED,
                approved_by=3,  # Bob Approver
                approved_at=datetime.utcnow() - timedelta(days=1),
                denial_reason="Insufficient justification. Please provide incident ticket number.",
                is_break_glass=False,
                created_at=datetime.utcnow() - timedelta(days=1, hours=1)
            ),
            models.AccessRequest(
                user_id=5,  # Diana Requester
                resource_id=4,  # prod-api
                duration_seconds=3600,
                justification="Urgent: Investigate production API latency spike. Incident #5678",
                status=models.RequestStatus.APPROVED,
                approved_by=2,  # Alice Approver
                approved_at=datetime.utcnow() - timedelta(minutes=30),
                is_break_glass=True,
                created_at=datetime.utcnow() - timedelta(minutes=35)
            ),
            models.AccessRequest(
                user_id=4,  # Charlie Requester
                resource_id=6,  # staging-db
                duration_seconds=14400,
                justification="Performance testing and optimization work on staging database",
                status=models.RequestStatus.PENDING,
                is_break_glass=False,
            ),
        ]
        
        for req in access_requests:
            db.add(req)
            print(f"Created access request: {req.id} - Status: {req.status.value}")
        
        db.commit()
        
        # Create audit events for the requests
        audit_events = [
            models.AuditEvent(
                event_type="REQUEST_CREATED",
                user_id=4,
                resource_id=1,
                request_id=1,
                event_metadata={"duration_seconds": 3600},
                timestamp=datetime.utcnow() - timedelta(hours=3)
            ),
            models.AuditEvent(
                event_type="REQUEST_APPROVED",
                user_id=2,
                resource_id=1,
                request_id=1,
                event_metadata={"approver_id": 2, "requester_id": 4},
                timestamp=datetime.utcnow() - timedelta(hours=2)
            ),
            models.AuditEvent(
                event_type="REQUEST_CREATED",
                user_id=5,
                resource_id=3,
                request_id=2,
                event_metadata={"duration_seconds": 7200},
                timestamp=datetime.utcnow() - timedelta(hours=2)
            ),
            models.AuditEvent(
                event_type="REQUEST_APPROVED",
                user_id=2,
                resource_id=3,
                request_id=2,
                event_metadata={"approver_id": 2, "requester_id": 5},
                timestamp=datetime.utcnow() - timedelta(hours=1)
            ),
        ]
        
        for event in audit_events:
            db.add(event)
        
        db.commit()
        
        print("\n" + "="*50)
        print("Database seeded successfully!")
        print("="*50)
        print("\nAPI Keys for testing:")
        for user in users:
            print(f"{user.email:30} ({user.role.value:10}): {user.api_key}")
        print("\nUse these API keys in the X-API-Key header for authentication")
        print("Example: curl -H 'X-API-Key: <key>' http://localhost:8000/api/v1/requests")
        
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()

