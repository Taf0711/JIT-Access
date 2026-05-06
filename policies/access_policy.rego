package jit.access

import future.keywords.if
import future.keywords.in

default allow_request = false
default allow_approval = false

weekday_numbers := {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

allow_request if {
    input.request
    input.policy
    input.request.duration_seconds <= object.get(input.policy, "max_ttl_seconds", 86400)
    break_glass_ttl_allowed
    no_access_days_allowed
    business_hours_allowed
}

break_glass_ttl_allowed if {
    not input.request.is_break_glass
}

break_glass_ttl_allowed if {
    input.request.is_break_glass
    input.request.duration_seconds <= 1800
}

no_access_days_allowed if {
    restrictions := object.get(input.policy, "time_window_restrictions", {})
    count(object.get(restrictions, "no_access_days", [])) == 0
}

no_access_days_allowed if {
    restrictions := object.get(input.policy, "time_window_restrictions", {})
    no_access_days := object.get(restrictions, "no_access_days", [])
    weekday_name := time.weekday(time.now_ns())
    weekday_number := weekday_numbers[weekday_name]
    not weekday_name in no_access_days
    not weekday_number in no_access_days
}

business_hours_allowed if {
    restrictions := object.get(input.policy, "time_window_restrictions", {})
    not object.get(restrictions, "business_hours_only", false)
}

business_hours_allowed if {
    restrictions := object.get(input.policy, "time_window_restrictions", {})
    object.get(restrictions, "business_hours_only", false)
    clock := time.clock(time.now_ns())
    clock[0] >= 9
    clock[0] < 17
}

allow_approval if {
    input.approver
    input.request
    input.approver.user_id != input.request.requester_id
    approver_role_allowed
    not input.approver.user_id in object.get(input, "existing_approvals", [])
}

approver_role_allowed if {
    rules := object.get(input.policy, "approval_rules", {})
    allowed_roles := object.get(rules, "allowed_roles", ["approver", "admin"])
    input.approver.role in allowed_roles
}

violation[msg] if {
    input.request.duration_seconds > object.get(input.policy, "max_ttl_seconds", 86400)
    msg := sprintf("Requested duration exceeds maximum TTL of %d seconds for this resource", [object.get(input.policy, "max_ttl_seconds", 86400)])
}

violation[msg] if {
    input.request.is_break_glass
    input.request.duration_seconds > 1800
    msg := "Break-glass access cannot exceed 1800 seconds"
}

violation[msg] if {
    restrictions := object.get(input.policy, "time_window_restrictions", {})
    no_access_days := object.get(restrictions, "no_access_days", [])
    weekday_name := time.weekday(time.now_ns())
    weekday_number := weekday_numbers[weekday_name]
    weekday_name in no_access_days
    msg := "Access is not allowed today by policy"
}

violation[msg] if {
    restrictions := object.get(input.policy, "time_window_restrictions", {})
    no_access_days := object.get(restrictions, "no_access_days", [])
    weekday_name := time.weekday(time.now_ns())
    weekday_number := weekday_numbers[weekday_name]
    weekday_number in no_access_days
    msg := "Access is not allowed today by policy"
}

violation[msg] if {
    restrictions := object.get(input.policy, "time_window_restrictions", {})
    object.get(restrictions, "business_hours_only", false)
    clock := time.clock(time.now_ns())
    clock[0] < 9
    msg := "Access is only allowed during business hours"
}

violation[msg] if {
    restrictions := object.get(input.policy, "time_window_restrictions", {})
    object.get(restrictions, "business_hours_only", false)
    clock := time.clock(time.now_ns())
    clock[0] >= 17
    msg := "Access is only allowed during business hours"
}

violation[msg] if {
    input.approver.user_id == input.request.requester_id
    msg := "Cannot approve your own request"
}

violation[msg] if {
    rules := object.get(input.policy, "approval_rules", {})
    allowed_roles := object.get(rules, "allowed_roles", ["approver", "admin"])
    not input.approver.role in allowed_roles
    msg := sprintf("Approver role '%s' is not allowed by policy", [input.approver.role])
}

violation[msg] if {
    input.approver.user_id in object.get(input, "existing_approvals", [])
    msg := "You have already approved this request"
}
