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

Dependency boundaries: domain contracts do not import API, model, or storage implementations; bootstrap wires concrete dependencies. Workflow proposes decisions; tools enforce scoped reads; policy authorizes; resolution executes and verifies; repositories persist. The model cannot write SQLite, modify policies, approve its own action, or read evaluation answers.

`scripts/demo_data.py` is the standard-library fixture validator and isolated-run seeder. `Repository` adds trusted session, ownership, revision, and operational storage when the run opens. The diagnostic agent uses a separate LangGraph SQLite checkpoint database. See the [implementation plan](IMPLEMENTATION_PLAN.md) for per-stage acceptance results.
