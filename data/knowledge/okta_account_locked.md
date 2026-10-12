# Locked Okta account

Article: KB-001 | Service: okta | Version: 1.0

Fictional demo procedure; no real vendor or company authorization is implied.

## Applicability

Repeated failures; account reports locked.

## Prerequisites

Use session-bound identity, current scoped evidence, and backend policy. Never collect passwords or OTPs.

## Procedure

1. Check account state and service status before another login attempt.
2. For a locked account, propose unlock_demo_account for the session employee after identity verification and consent.
3. Ask the employee to retry login once; if MFA still fails, investigate MFA separately.

## Verification

Account active AND employee confirms login.

## Escalation

Account disabled, suspected compromise, or failed authorized unlock.
