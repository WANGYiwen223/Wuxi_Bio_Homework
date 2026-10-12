# Policy

Fail-closed authorization, rule precedence and scoped approvals.

Implemented: `engine.py` derives authorization facts from trusted repositories and evidence; `approvals.py` stores proposals and scope-bound manager decisions, rejects expiry/replay, and rechecks current rules. No action executor is implemented yet.
