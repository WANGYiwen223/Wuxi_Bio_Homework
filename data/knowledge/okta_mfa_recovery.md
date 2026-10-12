# MFA device unavailable

Article: KB-002 | Service: okta | Version: 1.0

Fictional demo procedure; no real vendor or company authorization is implied.

## Applicability

Active account with missing MFA device.

## Prerequisites

Use session-bound identity, current scoped evidence, and backend policy. Never collect passwords or OTPs.

## Procedure

1. Ask whether the enrolled MFA device is available; never request an OTP or password.
2. Confirm account state and distinguish MFA from password failure.
3. Hand off identity recovery to IT; no automated MFA bypass exists.

## Verification

IT-confirmed recovery and employee login.

## Escalation

MFA recovery requires identity specialist.
