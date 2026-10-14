# Candidate Instructions: Requirement-by-Requirement Audit

Audited on **2026-10-12** against [the supplied HTML](../agentic_ai_take_home_candidate_instructions_v20260421_01.html), current code/fixtures, tests, and saved live reports. Section order follows the HTML. Examples and aspirational goals are distinguished from required deliverables; optional production integrations are not treated as missing mandatory features.

The audit does not equate a prompt instruction with verified model behavior. **Met** means the specific item has the evidence described in its row. **Partial** means implementation or evidence exists, but an important part is missing/unverified. **Goal unproven** means the proposed product outcome has not been measured in real use. **Optional/deferred** means the HTML permits it as additional design work.

Verification during this audit:

- `.venv/Scripts/python.exe scripts/demo_data.py validate`: seven scenarios, 14 articles, seven policy rules, and fixture references validated.
- `.venv/Scripts/python.exe -m pytest -q`: **83 passed in 7.58 seconds**; deterministic tests use isolated local systems and model doubles.
- `.venv/Scripts/python.exe -m pip check`: no broken requirements in the current Python **3.13.5** environment. A clean installation on another machine was not performed.
- Saved live evaluations and their limitations are summarized in [EVALUATION.md](EVALUATION.md). The latest pipeline trial passed; the latest account-unlock trial failed at the provider boundary.

## Business Problem and Product Goal

| ID | HTML item | Status | Evidence and qualification |
|---|---|---|---|
| B1 | Build AI support for an employee's real IT problem, with practical engineering/product judgment | Met for demo scope | [README](../README.md) defines employee pain, authority, success criteria, assumptions, and limits. Backends are synthetic as requested. |
| B2 | Understand the problem through conversation | Partial | Multi-turn messages, clarifying tool, and checkpoint continuity exist; [workflow tests](../tests/integration/test_workflow.py) verify scripted clarification. Free-form diagnostic clarification still needs live validation (G2). |
| B3 | Investigate using knowledge, status, and historical data | Met | [Read tools](../src/helpdesk/tools/read_tools.py) expose all three; the pipeline trial obtained runbooks, service/change/build/report evidence, and competing historical causes. |
| B4 | Resolve directly where possible, including instructions/information | Met within stated scope | [Resolution service](../src/helpdesk/resolution/service.py) and [runtime feedback](../src/helpdesk/bootstrap/runtime.py) support mock actions and documented guidance. Live unlock, VPN and access successes exist; guidance quality has narrower validation. |
| B5 | Escalate only when needed, preserving context so the employee does not repeat it | Partial | [Handoff service](../src/helpdesk/escalation/service.py) persists available context and distinguishes queue/acknowledgement. Production repairs and failure fallback were exercised; the quality of every escalation judgment is not established (G5). |
| B6 | Eliminate the queue for a majority of common issues; reduce hours to minutes | Goal unproven | Self-service bypasses an initial human queue in the demo. Synthetic timings and seven scenarios cannot establish majority-case resolution or real time saved (G6). |
| B7 | Employee's first/primary contact; multi-turn diagnosis and natural conversation rather than a form | Met for interaction design; validation partial | [UI](../ui/index.html) accepts chat text and explicit consent/feedback; backend keeps cases internally. Human interaction/visual QA and unplanned-input rehearsal remain open (G2/G3). |

## Core Use Case: Five Example Conversations

The HTML gives illustrative conversations rather than requiring exhaustive vendor integrations. Four categories have live evidence. The application accepts new problem text; fixture scenarios are backend conditions, not canned model replies.

| ID | HTML example | Status | Evidence and remaining gap |
|---|---|---|---|
| C1 | Okta login failure after reset, urgently before a meeting | Partial | Locked account source, KB and controlled unlock exist. A live trial passed; the latest trial failed before tool use. Urgency/deadline handling and the exact meeting variant were not evaluated (G2/G4). |
| C2 | Salesforce slow since yesterday for Chicago teammates | Partial | [KB-007](../data/knowledge/salesforce_regional_latency.md), Salesforce status and `HIST-005` exist. Current status is healthy; no dedicated slowdown incident/diagnostic fixture, evaluator prompt, or live trial exists (G1). |
| C3 | Remote VPN disconnects every 10–15 minutes | Met for tested variants | Live stale-profile resolution, outage handoff, conflicting-evidence and timeout trials. Some fallback passes include provider failure; see [evaluation](EVALUATION.md). |
| C4 | New Data Engineering employee needs Snowflake PROD and Grafana | Met | Live two-resource trial resolved; manager approval recorded for PROD. [API tests](../tests/integration/test_api.py) prohibit closure after only one resource. |
| C5 | Friday maintenance followed by Jenkins timeouts and stale Tableau | Met | Latest live trial collected `CHG-001`, `BUILD-001`, `REPORT-001` and queued a contextual SRE handoff without mutation. Root cause remained a hypothesis; production repair is outside authority. |

## Data & Environment

| ID | HTML source/condition | Status | Evidence and purpose |
|---|---|---|---|
| D1 | Mock knowledge articles, FAQs/runbooks/troubleshooting | Met | [Knowledge index](../data/knowledge/index.json) and 14 Markdown articles; indexed lexical search and article loading. |
| D2 | Mock current health, outages, and recent changes | Met | [Services](../data/fixtures/services.json), [incidents](../data/fixtures/incidents.json), [changes](../data/fixtures/changes.json), scenario overrides; source timestamps preserved. |
| D3 | Mock employee department, role, location, equipment and permissions | Met | [Employees](../data/fixtures/employees.json), [devices](../data/fixtures/devices.json), [grants](../data/fixtures/access_grants.json); reads scoped to backend session identity. |
| D4 | Searchable past resolutions | Met | Nine [history records](../data/fixtures/resolution_history.json), lexical search, competing network/credential explanations. |
| D5 | Rules defining authority and human approval | Met | Seven [rules](../data/policies/action_rules.json), default deny and scoped manager approval; [policy tests](../tests/integration/test_policy_approvals.py). |
| D6 | At least 2–3 realistic synthetic source categories | Met | All five suggested categories plus diagnostic snapshots are included. Records are fictional and labelled accordingly. |
| D7 | Small but rich enough for multi-source reasoning | Met | Seven scenarios include changes, stale status, faults, multi-resource requests and ambiguous causes; pipeline live evidence corroborates meaningful source use. |

## Problem Framing Requirements

These six rows audit the explicit framing in the submission, not a guarantee of every runtime outcome.

| ID | HTML framing item | Status | Location |
|---|---|---|---|
| F1 | Define the user as an employee rather than helpdesk staff | Met | [README: problem and user](../README.md#problem-user-and-success-criteria); reviewer is secondary. |
| F2 | Define the interaction model | Met | Browser chat, FastAPI, consent/feedback controls and separate reviewer panel in README. |
| F3 | Explain direct resolution versus human escalation | Met | [README boundary table](../README.md#resolution-and-escalation-boundary) specifies allowed fixes, approval and production repair. |
| F4 | Describe queried sources and how they are used | Met | [README data/I/O table](../README.md#simulated-data-and-agent-io) and [architecture](../IT_HELPDESK_ARCHITECTURE.md). |
| F5 | Define success from the employee's perspective | Met | Verified/confirmed fix, whole-issue closure and useful handoff; two-minute target explicitly distinguished from measured SLA. |
| F6 | Define full-context human handoff | Met | README lists context fields, support groups and acknowledgement semantics; [handoff tests](../tests/integration/test_handoff.py). |

## What We Are Looking For

| ID | HTML engineering capability | Status | Evidence and qualification |
|---|---|---|---|
| Q1 | Conversational diagnosis and clarifying questions | Partial | Model-selected `finish_turn(kind=clarify)` and unresolved questions are implemented; scripted multi-turn/restart test passes. No dedicated live vague/incomplete conversation suite (G2). |
| Q2 | Multi-step reasoning: gather sources, form/refine hypotheses | Met for demonstrated cases | Pipeline model made three calls and 13 tool calls, comparing current timeout/no-auth-error evidence against maintenance and two historical causes. Hypothesis quality is not comprehensively scored (G5). |
| Q3 | Tool use in reasoning workflow | Met | Seven read tools plus clarification, consent, requirements, proposal and handoff tools; live provider compatibility and actual model-selected calls. |
| Q4 | State/memory for conversation, investigations and unresolved work | Met | Owned case/messages/evidence, recorded questions, attempts, required resources and [LangGraph checkpoints](../src/helpdesk/workflow/agent.py); restart and interrupted-call tests. |
| Q5 | Resolution versus escalation judgment and complete summary | Partial | Deterministic authority/verification, scoped approvals and context handoff verified. Human review of handoff accuracy and unjustified escalation rate is absent (G5). |
| Q6 | Vague descriptions, missing info, conflicting data, tool failures | Partial | Missing-result, conflict, timeout and budget tests pass; live conflict/failure handoffs preserve evidence. Vague descriptions and missing articles lack live acceptance tests (G2). |
| Q7 | Avoid fabrication and unauthorized actions; transparent confidence | Partial | Backend identity/policy gates and strict action schemas are tested; prompt requires sources and candid uncertainty. Free-text citation validity, unsupported advice and prompt-injection resistance are not independently enforced/evaluated (G2/G5). |
| Q8 | Deliberate evaluation of correct resolution and escalation | Met as an evaluation method; quality partial | [Scorer](../src/helpdesk/evaluation/scoring.py), [expected outcomes](../tests/conversations/expected_outcomes.json), deterministic tests and isolated live trials exist. Structural checks can pass a generic failure handoff and do not grade diagnostic text (G5). |
| Q9 | Consider observability, cost, latency and maintainability | Met for consideration and basic instrumentation | Persisted audits/metadata traces, call/token counts, timings, budgets, modular boundaries and pinned environment. Monetary cost, latency distributions, production monitoring and retention are deferred. |

The HTML explicitly permits imperfect coverage and values tradeoffs over feature count. A partial row is a limitation to disclose, not an assertion that production integrations are mandatory.

## Deliverables

| ID | HTML deliverable/item | Status | Evidence and qualification |
|---|---|---|---|
| R0 | Runnable code repository with clear setup | Partial | [README setup](../README.md#setup-and-local-run), declared/pinned dependencies, seed/probe/server commands; current environment tests and dependency check pass. Clean-machine install and browser rehearsal remain unverified (G3). |
| R1 | README: problem chosen and why | Met | Problem/user section explains repeated, employee-specific issues and support delays. |
| R2 | README: why agentic rather than chatbot/FAQ/rules | Met | Agentic rationale explains competing diagnoses, changing evidence and conversational steps; rules enforce authority. |
| R3 | README: architecture and decisions | Met | Diagram, responsibility table, single agent, lexical retrieval, SQLite, checkpoint/idempotency decisions. |
| R4 | README: resolution/escalation boundary | Met | Per-issue authority table and verification/handoff lifecycle. |
| R5 | README: simulated data and why | Met | Five suggested source categories plus diagnostics; typed read/write I/O and purposes. |
| R6 | README: assumptions and tradeoffs | Met | Fixture identities, local concurrency, fixed clock, small corpus, limited actions and guidance-verification limits. |
| R7 | README: how to run | Met as instructions | PowerShell environment/dependency/config/seed/probe/server and scenario-switch instructions; cross-machine execution remains G3. |
| R8 | README: evaluation | Met | Deterministic/live distinction, commands, latest trials, failures, timing/tokens and scorer limitations. |
| R9 | README: improvements with more time | Met | Prioritized validation and reliability work, followed by production direction. |
| R10 | Interview walkthrough; live preferred, recording acceptable | Partial | [Demo guide](DEMO_GUIDE.md) and runtime exist. No recorded demo or completed browser interview rehearsal (G3); live provider reliability remains G4. |
| R11 | Interviewers type new problems, rather than only fixed examples | Partial | Message API accepts arbitrary text and model selects tools. Unplanned-input live evaluation is missing; seven current scenarios alone are insufficient evidence (G2). |
| R12 | Optional production design note: chat integration, SSO, audits, human-service integration | Met as design; integrations optional/deferred | README describes SSO, Slack/Teams, least-privilege APIs, retention/monitoring and ServiceNow handoff. Local audit logging exists; external integrations do not. |

## Technical Guidance

| ID | HTML guidance | Status | Evidence and qualification |
|---|---|---|---|
| T1 | Any preferred frameworks/libraries/models/APIs | Met | LangGraph, FastAPI, Pydantic, SQLite and an interchangeable chat-completions adapter; provider not hardcoded. |
| T2 | Runnable locally | Met in existing environment; portability partial | API and tests run locally; the model may be remote. A local inference server can be configured but has not been tested. Clean install is G3. |
| T3 | Reasonable, clearly documented external dependencies | Met | [pyproject.toml](../pyproject.toml), [requirements.lock](../requirements.lock), README direct dependencies and provider/network requirements. No enterprise service or frontend build dependency. |
| T4 | Engineering clarity rather than maximum feature breadth | Met | Explicit component ownership, limited action vocabulary, documented deferred integrations and validation limits. |

## Interview Session Preparation

| ID | HTML walkthrough topic | Status | Prepared evidence / remaining work |
|---|---|---|---|
| I1 | Chosen IT problem and scope | Met as preparation | README user/problem and boundary table. |
| I2 | Architecture and implementation | Met as preparation | Architecture diagram, detailed architecture, component code and module ownership. |
| I3 | Live new-problem demo and employee conversation | Partial | Demo instructions and generic message endpoint exist; G2/G3/G4 affect readiness. |
| I4 | Ambiguous, incomplete and out-of-scope requests | Partial | Clarification, missing outcomes and default-deny tests exist; live conversation evidence remains G2. |
| I5 | Escalation and preserved human context | Met for demonstrated flow | Pipeline live evidence and contextual queue, plus role-scoped acknowledgement tests; summary quality caveat G5. |
| I6 | Evaluation results and failure cases | Met | README and evaluation retain wrong-action-schema failures, provider failures, successful repairs, and fallback limits. |
| I7 | Improvements and productionization | Met as preparation | Prioritized README improvements and optional production design. |

## What Good Submissions Usually Show

| ID | HTML signal | Status | Cross-reference |
|---|---|---|---|
| S1 | Clear employee-facing support experience | Met for design; UX partial | B7, F1/F2; interaction QA G3. |
| S2 | Conversational diagnostic workflow beyond one LLM call | Met | Q2–Q4; live pipeline and multi-resource traces show several calls and tool decisions. |
| S3 | Clarifying questions and progress toward resolution | Partial | Q1; consent/feedback live turns exist, but open-ended diagnostic clarification needs G2. |
| S4 | Meaningful orchestration of KB/status/user tools | Met | Q2/Q3 and pipeline evidence. |
| S5 | Clear resolution versus escalation judgment | Partial | F3 is documented; runtime quality across new cases remains Q5/G5. |
| S6 | Edge cases: vague input, missing articles, conflicting information | Partial | Q6; missing live vague/article trials are G2. |
| S7 | Concrete test conversations and expected outcomes | Met for current scope; coverage partial | Seven evaluator prompts, expected-outcome file, saved trials; Salesforce and fresh-input gaps G1/G2. |
| S8 | Candid tradeoffs, exclusions and reasons | Met | README limitations, evaluation failures and this audit. |

## Remaining Work, Ordered for Interview Readiness

| Gap | Priority | What is missing | Acceptance evidence to add |
|---|---|---|---|
| G1 | High | End-to-end Salesforce/Chicago slowdown example | Add current incident/diagnostic scenario and expected outcome; test scoped status/history retrieval; run a live multi-turn trial that obtains regional evidence and gives supported guidance or a contextual handoff. |
| G2 | High | Real-model handling of fresh/vague/incomplete/missing-article/out-of-scope inputs | Add varied, held-out conversations, including urgency, declined consent and untrusted-source instructions. Demonstrate focused questions, preserved answers, honest unknowns and no unauthorized effects; distinguish live trials from model doubles. |
| G3 | High | Browser interaction and reproducible setup rehearsal | Verify README from a fresh environment; manually exercise employee chat, consent, feedback, scoped approval and handoff acknowledgement. Record results or prepare a recording if live tooling remains unavailable. Existing API tests are narrower evidence. |
| G4 | High | Provider stability for a live interview | Rerun account unlock and several repeat trials; retain failures and report reliability/latency. Choose and test bounded recovery that does not replay mutations. Latest unlock failure and earlier pipeline timeouts remain unresolved reliability evidence. |
| G5 | Medium | Semantic quality of diagnosis, citations and escalation summaries | Extend evaluation to source relevance, factual/citation validity, hypotheses versus confirmed causes, missing impact/questions, unsupported guidance and appropriate escalation reason/routing. Current structural scores are insufficient for these claims. |
| G6 | Future measurement | Majority resolution, real two-minute outcomes, and dollar cost | Measure broader representative cases and actual employee response time, benchmark latency distributions, and use verified provider billing/pricing data. Do not turn current synthetic samples into a production KPI. |
| G7 | Optional production work | SSO, chat/service integrations, enterprise APIs, deployment controls | Design is documented; implementation is deferred in keeping with the local mocked-backend scope. |

This audit changed documentation only. It does not implement the missing scenarios or turn unverified behaviors into passing requirements.
