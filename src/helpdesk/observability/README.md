# Observability

Redacted traces, latency and model/tool usage.

`redaction.py` masks common labelled secrets. Committed repository audit events
feed workflow progress, the case-scoped developer inspector, and JSON-line logs
on stderr and in the active run's rotating `app.log`. Events include model/tool
starts and completions, turn/call IDs, usage, latency and sanitized failure types;
they exclude prompts, tool arguments and result bodies. `presentation.py` projects
these events into employee-facing steps and resolves internal evidence references
to numbered source cards. Production monitoring and billing-aware cost measurement remain deferred.
