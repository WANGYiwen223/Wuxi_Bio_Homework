# Snowflake production reader access

Article: KB-008 | Service: snowflake | Version: 1.0

Fictional demo procedure; no real vendor or company authorization is implied.

## Applicability

Data Engineering employee requests PROD reader.

## Prerequisites

Use session-bound identity, current scoped evidence, and backend policy. Never collect passwords or OTPs.

## Procedure

1. Check department and existing grants.
2. Evaluate policy for snowflake-prod, PROD, reader; capture business justification.
3. Record an action proposal and wait for the employee's manager approval before execution; verify the resulting grant and read probe.

## Verification

Approved reader grant and successful probe.

## Escalation

Writer access, department mismatch, or rejected approval.
