# Candidate Instructions: Requirement-by-Requirement Audit

Audited on **2026-10-12**, condensed **2026-10-14**, against [the supplied HTML](../agentic_ai_take_home_candidate_instructions_v20260421_01.html), current code/fixtures, tests, and saved live reports. Section order follows the HTML. Optional production integrations are not treated as missing mandatory features.

**Met** = the item has the evidence described. **Partial** = implementation or evidence exists, but an important part is missing/unverified. **Goal unproven** = the proposed product outcome has not been measured in real use. **Optional/deferred** = the HTML permits it as additional design work. A prompt instruction is not equated with verified model behavior.

Verification during the audit:

- `scripts/demo_data.py validate`: nine scenarios, 14 articles, seven policy rules, and fixture references validated.
- `pytest -q`: **121 passed** (2026-10-14); deterministic tests use isolated local systems and model doubles.
- `pip check`: no broken requirements in the current Python **3.13.5** environment; a clean install on another machine was not performed.
- Saved live evaluations and their limitations: [EVALUATION.md](EVALUATION.md). The version-2 live matrix (2026-10-14) passed 13 of 14 trials, including both account-unlock trials; one conflicting-evidence trial failed its handoff check.

## Business Problem and Product Goal

| ID | HTML item | Status | Evidence and qualification |
|---|---|---|---|
| B1 | AI support for a real employee IT problem | Met for demo scope | [README](../README.md) defines employee pain, authority, success criteria, assumptions, limits. Backends are synthetic as requested. |
| B2 | Understand the problem through conversation | Partial | Multi-turn messages, clarifying tool, checkpoint continuity exist; scripted clarification tested. Free-form diagnostic clarification needs live validation (G2). |
| B3 | Investigate using knowledge, status, history | Met | Read tools expose all three; the pipeline trial obtained runbooks, service/change/build/report evidence, and competing historical causes. |
| B4 | Resolve directly where possible | Met within stated scope | Mock actions and documented guidance implemented; live unlock/VPN/access successes exist; guidance quality has narrower validation. |
| B5 | Escalate only when needed, preserving context | Partial | Handoff persists context and distinguishes queue/acknowledgement; the quality of every escalation judgment is not established (G5). |
| B6 | Eliminate the queue for a majority of issues; hours → minutes | Goal unproven | Self-service bypasses an initial human queue in the demo; synthetic timings cannot establish majority resolution or real time saved (G6). |
| B7 | Employee's first contact; conversation rather than a form | Met for design; validation partial | Chat UI with consent/feedback controls; backend keeps cases internally. Interaction QA and unplanned-input rehearsal open (G2/G3). |

## Core Use Case: Five Example Conversations

| ID | HTML example | Status | Evidence and remaining gap |
|---|---|---|---|
| C1 | Okta login failure after reset, urgently before a meeting | Partial | Locked-account source, KB, and controlled unlock exist; both version-2 matrix trials resolved. Urgency/deadline handling not evaluated (G2/G4). |
| C2 | Salesforce slow since yesterday for Chicago teammates | Partial | KB-007, Salesforce status, and HIST-005 exist; no dedicated slowdown incident fixture, evaluator prompt, or live trial (G1). |
| C3 | Remote VPN disconnects every 10–15 minutes | Met for tested variants | Version-2 matrix: stale-profile and timeout trials resolved, regional-outage handoffs passed without mutation; conflicting evidence passed one of two (failure retained). |
| C4 | New Data Engineering employee needs Snowflake PROD and Grafana | Met | Live two-resource trial resolved; manager approval recorded for PROD; API tests prohibit closure after only one resource. |
| C5 | Friday maintenance → Jenkins timeouts and stale Tableau | Met | Latest live trial collected CHG-001, BUILD-001, REPORT-001 and queued a contextual SRE handoff without mutation; root cause remained a hypothesis. |

## Data & Environment

| ID | HTML source/condition | Status | Evidence |
|---|---|---|---|
| D1 | Mock knowledge articles / runbooks | Met | 14 indexed Markdown articles under `data/knowledge/`. |
| D2 | Mock health, outages, recent changes | Met | `services.json`, `incidents.json`, `changes.json`, scenario overrides; source timestamps preserved. |
| D3 | Mock employee department/role/location/equipment/permissions | Met | `employees.json`, `devices.json`, `access_grants.json`; reads scoped to backend session identity. |
| D4 | Searchable past resolutions | Met | Nine history records with competing network/credential explanations. |
| D5 | Rules defining authority and human approval | Met | Seven rules, default deny, scoped manager approval; policy tests. |
| D6 | At least 2–3 realistic synthetic source categories | Met | All five categories plus diagnostic snapshots; records fictional and labelled. |
| D7 | Small but rich enough for multi-source reasoning | Met | Scenarios include changes, stale status, faults, multi-resource requests, ambiguous causes; pipeline live evidence corroborates source use. |

## Problem Framing Requirements

| ID | HTML framing item | Status | Location |
|---|---|---|---|
| F1 | User defined as employee, not helpdesk staff | Met | [README](../README.md) problem section; reviewer is secondary. |
| F2 | Interaction model defined | Met | Browser chat, FastAPI, consent/feedback controls, separate reviewer panel. |
| F3 | Direct resolution versus human escalation explained | Met | README boundary table. |
| F4 | Queried sources and their use described | Met | README data table and [architecture](../IT_HELPDESK_ARCHITECTURE.md). |
| F5 | Success from the employee's perspective | Met | Verified/confirmed fix, whole-issue closure, useful handoff; two-minute target distinguished from measured SLA. |
| F6 | Full-context human handoff defined | Met | README lists context fields, support groups, acknowledgement semantics; handoff tests. |

## What We Are Looking For

| ID | HTML capability | Status | Evidence and qualification |
|---|---|---|---|
| Q1 | Conversational diagnosis and clarifying questions | Partial | Model-selected clarification implemented; scripted multi-turn/restart test passes. No dedicated live vague-input suite (G2). |
| Q2 | Multi-step reasoning over sources and hypotheses | Met for demonstrated cases | Pipeline trial: 3 model calls, 13 tool calls, comparing current evidence against maintenance and two historical causes. Hypothesis quality not comprehensively scored (G5). |
| Q3 | Tool use in a reasoning workflow | Met | Seven read tools plus clarification/consent/requirements/proposal/handoff tools; live provider compatibility confirmed. |
| Q4 | State/memory for conversations and investigations | Met | Owned case/messages/evidence, recorded questions/attempts, LangGraph checkpoints; restart and interrupted-call tests. |
| Q5 | Resolution versus escalation judgment and summary | Partial | Authority/verification/approvals/handoff verified; human review of handoff accuracy and unjustified-escalation rate absent (G5). |
| Q6 | Vague descriptions, missing info, conflicting data, tool failures | Partial | Missing-result, conflict, timeout, budget tests pass; live conflict/failure handoffs preserve evidence; one version-2 conflicting-evidence trial exhausted its turns awaiting employee input and failed its handoff check (retained). Vague inputs and missing articles lack live acceptance tests (G2). |
| Q7 | Avoid fabrication and unauthorized actions; transparent confidence | Partial | Backend identity/policy gates and strict action schemas tested. Free-text citation validity, unsupported advice, and prompt-injection resistance not independently enforced/evaluated (G2/G5). |
| Q8 | Deliberate evaluation of resolution and escalation | Met as method; quality partial | Scorer, expected outcomes, deterministic tests, isolated live trials. Structural checks can pass a generic failure handoff and do not grade diagnostic text (G5). |
| Q9 | Observability, cost, latency, maintainability | Met for consideration and basic instrumentation | Persisted audits/traces, call/token counts, timings, budgets, modular boundaries, pinned environment. Monetary cost, latency distributions, production monitoring deferred. |

## Deliverables

| ID | HTML deliverable | Status | Evidence and qualification |
|---|---|---|---|
| R0 | Runnable repository with clear setup | Partial | [README](../README.md) setup, pinned dependencies, seed/probe/server commands; tests and dependency check pass here. Clean-machine install and browser rehearsal unverified (G3). |
| R1–R9 | README topics: problem, agentic rationale, architecture, boundary, data, assumptions, run, evaluation, improvements | Met | README covers all nine requested topics. |
| R10 | Interview walkthrough (live preferred) | Partial | [Demo guide](DEMO_GUIDE.md) and runtime exist; no recorded demo or completed browser rehearsal (G3); live provider reliability (G4). |
| R11 | Interviewers can type new problems | Partial | The message API accepts arbitrary text and the model selects tools; unplanned-input live evaluation missing (G2). |
| R12 | Optional production design note | Met as design; integrations optional/deferred | README describes SSO, Slack/Teams, least-privilege APIs, retention/monitoring, ServiceNow handoff. |

## Technical Guidance and Interview Preparation

| ID | HTML item | Status | Evidence |
|---|---|---|---|
| T1 | Any preferred frameworks/models | Met | LangGraph, FastAPI, Pydantic, SQLite, interchangeable chat-completions adapter. |
| T2 | Runnable locally | Met here; portability partial | API and tests run locally; the model may be remote. Clean install is G3. |
| T3 | Reasonable documented dependencies | Met | `pyproject.toml`, `requirements.lock`, README dependency notes. No enterprise service or frontend build dependency. |
| T4 | Engineering clarity over feature breadth | Met | Explicit ownership, limited action vocabulary, documented deferrals and validation limits. |
| I1–I7 | Walkthrough topics (problem, architecture, live demo, ambiguity, escalation, evaluation, improvements) | Met as preparation except I3/I4 partial | Demo instructions and generic message endpoint exist; G2/G3/G4 affect live readiness; pipeline handoff evidence covers I5; retained failures cover I6. |
| S1–S8 | "Good submission" signals | Met except S1 UX, S3 clarification, S5 judgment quality, S6 edge-case live coverage partial | Cross-references: B7, Q1, Q5, Q6, S7 (seven evaluator prompts and saved trials; G1/G2 gaps), S8 (candid tradeoffs in README/evaluation/this audit). |

## Remaining Work, Ordered for Interview Readiness

| Gap | Priority | What is missing | Acceptance evidence to add |
|---|---|---|---|
| G1 | High | End-to-end Salesforce/Chicago slowdown example | Incident/diagnostic scenario, expected outcome, live multi-turn trial with regional evidence and supported guidance or contextual handoff. |
| G2 | High | Real-model handling of fresh/vague/incomplete/missing-article/out-of-scope inputs | Varied held-out conversations (urgency, declined consent, untrusted-source instructions); focused questions, honest unknowns, no unauthorized effects. |
| G3 | High | Browser interaction and reproducible setup rehearsal | Verify README from a fresh environment; manually exercise chat, consent, feedback, approval, handoff acknowledgement; record results. |
| G4 | High | Provider stability for a live interview | Rerun account unlock and repeat trials; retain failures; report reliability/latency; bounded recovery without replaying mutations. |
| G5 | Medium | Semantic quality of diagnosis, citations, escalation summaries | Score source relevance, citation validity, hypothesis-vs-confirmed causes, unsupported guidance, escalation reason/routing. |
| G6 | Future measurement | Majority resolution, real two-minute outcomes, dollar cost | Representative cases, actual employee timing, latency distributions, verified provider pricing. |
| G7 | Optional production work | SSO, chat/service integrations, enterprise APIs, deployment controls | Design documented; implementation deferred per the local mocked-backend scope. |

This audit changed documentation only. It does not implement the missing scenarios or turn unverified behaviors into passing requirements.
