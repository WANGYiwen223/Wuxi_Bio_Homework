# Repository Structure and Ownership

```text
src/helpdesk/
  bootstrap/       Configuration, dependency wiring, clock and demo session context
  domain/          Case state, tool envelopes, evidence, approval and action contracts
  api/             Employee and reviewer HTTP routes
  workflow/        LangGraph topology, nodes, transitions and investigation budgets
  models/          Model-provider adapter and structured decision parsing
  tools/           Model-visible typed tools and trusted-context gateway
  adapters/        Local mock data-source adapters; future enterprise adapters
  knowledge/       Markdown loading and lexical retrieval
  policy/          Deterministic authorization and approval lifecycle
  resolution/      Controlled action executor and independent verifier
  escalation/      Handoff creation, routing and acknowledgement
  storage/         SQLite repositories, migrations and checkpoint wiring
  observability/   Redacted trace events, latency and usage measurements
  evaluation/      Conversation runner and scoring
ui/               Minimal employee chat and separate reviewer surface
data/             Immutable synthetic sources, rules and scenario overrides
scripts/          Data authoring, validation and isolated demo seeding
tests/            Unit, integration and conversation-outcome evaluations
var/              Ignored generated databases, checkpoints and results
```

Directories retain ownership notes. Contracts, repositories, read tools, policy/approval, model/workflow, resolution, escalation, API/UI and evaluation modules are now implemented. See the implementation plan for per-stage acceptance results and documented limitations.

Dependency boundaries: domain contracts do not import API, model or storage implementations. Bootstrap wires concrete dependencies. Workflow proposes decisions; tools enforce scoped reads; policy authorizes; resolution executes and verifies; repositories persist. The model cannot write SQLite, modify policies, approve its own action, or read evaluation answers.

`scripts/demo_data.py` is the standard-library fixture validator and isolated-run seeder. It creates keyed JSON-record source tables and initial operational tables. `Repository` adds trusted session, ownership, revision and operational storage when the run opens. The diagnostic agent creates and uses a separate LangGraph SQLite checkpoint database.
