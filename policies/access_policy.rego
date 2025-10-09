package jit.access

import future.keywords.if
import future.keywords.in

# Default deny all access requests
default allow_request = false
default allow_approval = false

# Input structure:
# {
#   "request": {
#     "user_id": int,
#     "user_role": string,
#     "resource_id": int,
#     "resource_type": string,
#     "duration_seconds": int,
#     "is_break_glass": bool,
#     "resource_metadata": object
#   },
#   "policy": {
#     "max_ttl_seconds": int,
#     "approval_rules": object,
#     "time_window_restrictions": object
#   }
# }

# Allow request if all conditions are met
allow_request if {
    input.request
    input.policy
    
    # Check TTL doesn't exceed max
    input.request.duration_seconds <= input.policy.max_ttl_seconds
    
    # Check time window restrictions
    check_time_window
    
    # Break-glass requests must be flagged
    check_break_glass
}

# Check time window restrictions
check_time_window if {
    not input.policy.time_window_restrictions
}

check_time_window if {
    not input.policy.time_window_restrictions.no_access_days
}

check_time_window if {
    # Check if current day is not in no_access_days
    day_of_week := time.weekday(time.now_ns())
    restrictions := input.policy.time_window_restrictions
    not restrictions.no_access_days
}

check_time_window if {
    # If business_hours_only is not set, allow
    restrictions := input.policy.time_window_restrictions
    not restrictions.business_hours_only
}

# Break-glass checks
check_break_glass if {
    # Non-break-glass requests are OK
    not input.request.is_break_glass
}

check_break_glass if {
    # Break-glass must have shorter TTL (max 30 minutes)
    input.request.is_break_glass
    input.request.duration_seconds <= 1800
}

# Approval policy
# Input structure for approval:
# {
#   "approver": {
#     "user_id": int,
#     "role": string
#   },
#   "request": {
#     "requester_id": int,
#     "is_break_glass": bool,
#     "resource_id": int
#   },
#   "policy": {
#     "approval_rules": {
#       "min_approvers": int,
#       "allowed_roles": array
#     }
#   },
#   "existing_approvals": array
# }

# Allow approval if conditions met
allow_approval if {
    # Approver cannot approve their own request
    input.approver.user_id != input.request.requester_id
    
    # Approver must have correct role
    check_approver_role
    
    # Check if more approvals needed for break-glass
    check_break_glass_approvals
}

check_approver_role if {
    # Admin can always approve
    input.approver.role == "admin"
}

check_approver_role if {
    # Check if approver role is in allowed roles
    input.approver.role == "approver"
}

check_approver_role if {
    # Check against policy allowed roles
    input.policy.approval_rules.allowed_roles
    input.approver.role in input.policy.approval_rules.allowed_roles
}

check_break_glass_approvals if {
    # Non-break-glass only needs 1 approval
    not input.request.is_break_glass
}

check_break_glass_approvals if {
    # Break-glass needs 2 approvals
    input.request.is_break_glass
    count(input.existing_approvals) >= 1  # This would be the 2nd approval
}

# Violation reasons for debugging
violation[msg] if {
    input.request.duration_seconds > input.policy.max_ttl_seconds
    msg := sprintf("Duration %d exceeds max TTL %d", [input.request.duration_seconds, input.policy.max_ttl_seconds])
}

violation[msg] if {
    input.request.is_break_glass
    input.request.duration_seconds > 1800
    msg := "Break-glass access cannot exceed 30 minutes (1800 seconds)"
}

violation[msg] if {
    input.approver
    input.approver.user_id == input.request.requester_id
    msg := "Cannot approve your own request"
}

violation[msg] if {
    input.request.is_break_glass
    count(input.existing_approvals) < 1
    msg := "Break-glass requests require dual approval (2 approvers)"
}

