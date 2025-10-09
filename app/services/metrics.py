"""
Prometheus metrics for JIT Access system
"""
from prometheus_client import Counter, Histogram, Gauge, Info
import time
from functools import wraps


# Request metrics
access_requests_total = Counter(
    'jit_access_requests_total',
    'Total number of access requests',
    ['status', 'resource_type', 'is_break_glass']
)

# Approval metrics
approval_duration_seconds = Histogram(
    'jit_approval_duration_seconds',
    'Time taken for requests to be approved',
    buckets=(60, 300, 600, 1800, 3600, 7200, 14400)  # 1min to 4hrs
)

approvals_total = Counter(
    'jit_approvals_total',
    'Total number of approvals',
    ['approver_role', 'is_break_glass', 'decision']  # decision: approved/denied
)

# Grant metrics
active_grants_total = Gauge(
    'jit_active_grants_total',
    'Current number of active grants'
)

grants_issued_total = Counter(
    'jit_grants_issued_total',
    'Total number of grants issued',
    ['resource_type']
)

grants_revoked_total = Counter(
    'jit_grants_revoked_total',
    'Total number of grants revoked',
    ['reason']
)

# Token validation metrics
token_validations_total = Counter(
    'jit_token_validations_total',
    'Total number of token validations',
    ['result', 'resource_type']  # result: valid/invalid/revoked/expired
)

gateway_access_total = Counter(
    'jit_gateway_access_total',
    'Total number of gateway access attempts',
    ['result', 'path']  # result: granted/denied
)

# Policy evaluation metrics
policy_evaluations_total = Counter(
    'jit_policy_evaluations_total',
    'Total number of policy evaluations',
    ['policy_type', 'decision']  # policy_type: request/approval, decision: allow/deny
)

policy_violations_total = Counter(
    'jit_policy_violations_total',
    'Total number of policy violations',
    ['violation_type']
)

# API performance metrics
http_request_duration_seconds = Histogram(
    'jit_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint', 'status_code'],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
)

http_requests_total = Counter(
    'jit_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

# Audit metrics
audit_events_total = Counter(
    'jit_audit_events_total',
    'Total audit events logged',
    ['event_type', 'is_break_glass']
)

# System info
system_info = Info('jit_access_system', 'JIT Access system information')
system_info.info({
    'version': '1.0.0',
    'name': 'JIT Access & Policy Gateway'
})


# Decorator for timing functions
def timed_metric(histogram):
    """Decorator to time function execution and record in Prometheus histogram"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                histogram.observe(duration)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                histogram.observe(duration)
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class MetricsService:
    """Service for recording metrics"""
    
    @staticmethod
    def record_access_request(status: str, resource_type: str, is_break_glass: bool):
        """Record an access request"""
        access_requests_total.labels(
            status=status,
            resource_type=resource_type,
            is_break_glass=str(is_break_glass)
        ).inc()
    
    @staticmethod
    def record_approval(approver_role: str, is_break_glass: bool, decision: str, duration_seconds: float = None):
        """Record an approval decision"""
        approvals_total.labels(
            approver_role=approver_role,
            is_break_glass=str(is_break_glass),
            decision=decision
        ).inc()
        
        if duration_seconds and decision == "approved":
            approval_duration_seconds.observe(duration_seconds)
    
    @staticmethod
    def record_grant_issued(resource_type: str):
        """Record a grant issuance"""
        grants_issued_total.labels(resource_type=resource_type).inc()
    
    @staticmethod
    def record_grant_revoked(reason: str):
        """Record a grant revocation"""
        grants_revoked_total.labels(reason=reason).inc()
    
    @staticmethod
    def update_active_grants_count(count: int):
        """Update the active grants gauge"""
        active_grants_total.set(count)
    
    @staticmethod
    def record_token_validation(result: str, resource_type: str = "unknown"):
        """Record a token validation"""
        token_validations_total.labels(
            result=result,
            resource_type=resource_type
        ).inc()
    
    @staticmethod
    def record_gateway_access(result: str, path: str):
        """Record a gateway access attempt"""
        gateway_access_total.labels(
            result=result,
            path=path
        ).inc()
    
    @staticmethod
    def record_policy_evaluation(policy_type: str, decision: str):
        """Record a policy evaluation"""
        policy_evaluations_total.labels(
            policy_type=policy_type,
            decision=decision
        ).inc()
    
    @staticmethod
    def record_policy_violation(violation_type: str):
        """Record a policy violation"""
        policy_violations_total.labels(violation_type=violation_type).inc()
    
    @staticmethod
    def record_http_request(method: str, endpoint: str, status_code: int, duration: float):
        """Record an HTTP request"""
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).observe(duration)
    
    @staticmethod
    def record_audit_event(event_type: str, is_break_glass: bool):
        """Record an audit event"""
        audit_events_total.labels(
            event_type=event_type,
            is_break_glass=str(is_break_glass)
        ).inc()


# Export metrics service
metrics_service = MetricsService()

