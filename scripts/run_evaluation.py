"""Bounded live-model conversation evaluation with isolated synthetic systems."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import time
from uuid import uuid4
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.demo_data import seed
from helpdesk.bootstrap.context import DemoClock
from helpdesk.bootstrap.settings import Settings
from helpdesk.bootstrap.runtime import Runtime
from helpdesk.evaluation.scoring import score_case
from helpdesk.storage.repository import Repository

def evaluation_cases():
    # Actors and expectations belong to the evaluator, never scenario/source data.
    return json.loads((ROOT / "tests/conversations/expected_outcomes.json").read_text(encoding="utf-8"))


def run_one(name, employee_id, prompt, settings, max_turns):
    run_id = "eval-" + name + "-" + employee_id + "-" + uuid4().hex[:8]
    seed(name, run_id, employee_ids=[employee_id])
    directory = ROOT / "var/runs" / run_id
    manifest = json.loads((directory / "manifest.json").read_text())
    repo = Repository(directory / "helpdesk.sqlite")
    runtime = Runtime(repo, settings, DemoClock(datetime.fromisoformat(manifest["clock"])), ROOT / "data/knowledge", ROOT / "data/policies/action_rules.json", directory / "checkpoints.sqlite", faults=manifest["faults"])
    session = repo.create_demo_session(employee_id)
    case = repo.create_case(session, runtime.clock)
    ctx = runtime.context(session, case.case_id)
    text, turns, started = prompt, [], time.monotonic()
    try:
        for _ in range(max_turns):
            response = runtime.agent.turn(ctx, text)
            turns.append(response)
            current = repo.get_case(ctx)
            if current.status in {"resolved", "escalated"}:
                break
            if current.facts.get("pending_consent"):
                runtime.resolution.consent(ctx, current.facts["pending_consent"]["operation"], True)
                text = "I explicitly allowed the simulated action through the application. Please continue."
            elif current.status == "awaiting_approval":
                employee = repo.source("employees", ctx.employee_id)
                reviewer = repo.create_demo_session(employee["manager_id"])
                runtime.reviewer_decision(reviewer, current.facts["approval_id"], True)
                current = repo.get_case(ctx)
                if current.status == "awaiting_verification":
                    runtime.feedback(ctx, True)
                current = repo.get_case(ctx)
                if current.status in {"resolved", "escalated"}:
                    break
                text = "Please continue with any remaining requested resource."
            elif current.status == "awaiting_verification":
                runtime.feedback(ctx, True)
                if repo.get_case(ctx).status == "resolved":
                    break
                text = "Please continue with the remaining issue or resource."
            else:
                text = "I am using the assigned managed laptop, the symptom is unchanged, and MFA is available. " + prompt
        current = repo.get_case(ctx)
        with repo.transaction() as db:
            actions = [json.loads(row[0]) for row in db.execute("SELECT payload FROM actions WHERE json_extract(payload,'$.case_id')=?", (case.case_id,))]
            row = db.execute("SELECT payload FROM handoffs WHERE record_id=?", (current.handoff_id,)).fetchone() if current.handoff_id else None
            handoff = json.loads(row[0]) if row else None
        evidence = repo.evidence(ctx)
        scored = score_case(name, current.model_dump(mode="json"), evidence, actions, handoff)
        return {"scenario": name, "employee_id": employee_id, "fixture_version": manifest["fixture_version"], "mode": "live_model_with_simulated_employee_and_reviewer", "status": current.status, **scored, "duration_seconds": round(time.monotonic() - started, 2), "model_calls": sum(t["metrics"]["model_calls"] for t in turns), "tool_calls": sum(t["metrics"]["tool_calls"] for t in turns), "input_tokens": sum(t["metrics"]["input_tokens"] for t in turns), "output_tokens": sum(t["metrics"]["output_tokens"] for t in turns), "case_id": case.case_id, "run_directory": str(directory), "turns": turns}
    finally:
        runtime.close()


def main():
    cases = evaluation_cases()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", default=",".join(cases))
    parser.add_argument("--employees", help="Filter the configured evaluation actors (comma-separated)")
    parser.add_argument("--list", action="store_true", help="List selected trials without model calls or database writes")
    parser.add_argument("--max-turns", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.max_turns <= 6:
        parser.error("max-turns must be 1–6")
    names = args.scenarios.split(",")
    if any(name not in cases for name in names):
        parser.error("Unknown scenario")
    employees = set(args.employees.split(",")) if args.employees else None
    configured = {eid for name in names for eid in cases[name]["employee_ids"]}
    if employees is not None and not employees <= configured:
        parser.error("Employee is not a configured actor for the selected scenarios")
    trials = [(name, eid, cases[name]["prompt"]) for name in names for eid in cases[name]["employee_ids"] if employees is None or eid in employees]
    if args.list:
        for name, employee_id, prompt in trials:
            print(f"{name} / {employee_id}: {prompt}")
        return
    settings = Settings.load(ROOT)
    report = {"mode": "live_model", "note": "Synthetic employee feedback and manager decisions; actual model-selected tool calls. Not a production resolution-rate benchmark.", "results": []}
    output = ROOT / "var/evaluation"
    output.mkdir(parents=True, exist_ok=True)
    path = output / ("live-" + uuid4().hex[:8] + ".json")
    for name, employee_id, prompt in trials:
        result = run_one(name, employee_id, prompt, settings, args.max_turns)
        report["results"].append(result)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{name} / {employee_id}: status={result['status']}, passed={result['passed']}, calls={result['model_calls']}, seconds={result['duration_seconds']}", flush=True)
    print(f"Report: {path}", flush=True)


if __name__ == "__main__":
    main()
