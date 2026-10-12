# Application access denied

Article: KB-012 | Service: grafana | Version: 1.0

Fictional demo procedure; no real vendor or company authorization is implied.

## Applicability

User can log in but dashboard access fails.

## Prerequisites

Use session-bound identity, current scoped evidence, and backend policy. Never collect passwords or OTPs.

## Procedure

1. Separate authentication success from resource authorization.
2. Read current grants and exact resource policy.
3. Request only the supported role; do not grant admin to bypass an error.

## Verification

Authorized resource probe passes.

## Escalation

Resource unknown or privilege request unsupported.
