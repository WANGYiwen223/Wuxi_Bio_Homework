"""Model-visible read tools; scope and provenance are enforced by the gateway."""

from datetime import datetime
import json
from pathlib import Path
import sqlite3
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, ValidationError

from helpdesk.adapters.local import LocalSources
from helpdesk.bootstrap.context import ToolContext
from helpdesk.domain.contracts import EvidenceRecord, Source, ToolError, ToolResult, new_id
from helpdesk.knowledge.retrieval import KnowledgeBase, ranked
from helpdesk.storage.repository import AccessDenied, Repository


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyArgs(Args):
    pass


class SearchArgs(Args):
    query: str = Field(min_length=1, max_length=1000)
    service_id: str | None = None
    limit: Annotated[StrictInt, Field(ge=1, le=5)] = 3


class HistoryArgs(SearchArgs):
    environment: str | None = None


class ArticleArgs(Args):
    article_id: str


class StatusArgs(Args):
    service_id: str
    region: str | None = None


class ChangeArgs(Args):
    service_ids: list[str] = Field(min_length=1, max_length=7)
    since: AwareDatetime
    environment: str | None = None


class DiagnosticArgs(Args):
    service_id: str
    device_id: str | None = None
    resource_id: str | None = None


CATALOG = {
    "get_employee_context": (EmptyArgs, "Read the authenticated employee's department, roles, location, assigned devices, account states, access grants and readable shared diagnostic resources."),
    "search_knowledge": (SearchArgs, "Search fictional documented IT procedures. Search ranking is relevance, not diagnostic confidence."),
    "get_runbook": (ArticleArgs, "Read a selected documented procedure, including applicability and verification."),
    "get_service_status": (StatusArgs, "Read service health and incidents with timestamps and affected scope. Check scope before assuming impact."),
    "get_recent_changes": (ChangeArgs, "Find changes affecting listed services since an aware timestamp. Correlation alone does not establish cause."),
    "get_diagnostic_snapshot": (DiagnosticArgs, "Read personal device or authorized shared-resource observations. Optionally select device_id OR resource_id, never both. Shared resource IDs are listed by get_employee_context."),
    "search_resolution_history": (HistoryArgs, "Find previous resolutions with causes and verified outcomes; compare current evidence before applying a fix."),
}


class ReadTools:
    def __init__(self, repository: Repository, knowledge_directory: Path, faults: list[dict] | None = None):
        self.repository = repository
        self.sources = LocalSources(repository)
        self.knowledge = KnowledgeBase(knowledge_directory)
        self.faults = faults or []
        with repository.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS fault_counters (record_id TEXT PRIMARY KEY, count INTEGER NOT NULL)")

    def schemas(self) -> list[dict]:
        return [{"name": name, "description": description, "parameters": model.model_json_schema()} for name, (model, description) in CATALOG.items()]

    def _inject_fault(self, context, name, args):
        for index, fault in enumerate(self.faults):
            if fault["tool"] != name or any(args.get(k) != v for k, v in fault["match"].items()):
                continue
            key = f"{context.case_id}:{name}:{index}"
            with self.repository.transaction() as db:
                row = db.execute("SELECT count FROM fault_counters WHERE record_id=?", (key,)).fetchone()
                count = row[0] if row else 0
                db.execute("INSERT INTO fault_counters VALUES (?,?) ON CONFLICT(record_id) DO UPDATE SET count=excluded.count", (key, count + 1))
            if count < fault["fail_first_calls"]:
                raise TimeoutError("Configured demo timeout")

    @staticmethod
    def _source(kind, identifier, row):
        observed = row.get("observed_at") or row.get("updated_at") or row.get("resolved_at") or row.get("started_at")
        return Source(source_id=f"{kind}:{identifier}", source_type=kind, version=row.get("version", "fixture-v1"), observed_at=observed)

    def call(self, context: ToolContext, name: str, arguments: dict) -> ToolResult:
        call_id = new_id("CALL")
        evidence = []
        try:
            self.repository.get_case(context)
            if name not in CATALOG:
                raise ValueError("Unknown read tool")
            parsed = CATALOG[name][0].model_validate(arguments)
            self._inject_fault(context, name, parsed.model_dump())
            data, entries = self._dispatch(context, name, parsed)
            if data is None or data == []:
                result = ToolResult(tool_call_id=call_id, status="not_found", retrieved_at=context.clock.now(), error=ToolError(code="NOT_FOUND", message="No matching data; service state is unknown."))
            else:
                evidence = [EvidenceRecord(case_id=context.case_id, employee_id=context.employee_id, tool_name=name, tool_call_id=call_id, source=source, facts=facts, retrieved_at=context.clock.now()) for source, facts in entries]
                result = ToolResult(tool_call_id=call_id, status="success", data=data, sources=[s for s, _ in entries], evidence_ids=[e.evidence_id for e in evidence], retrieved_at=context.clock.now())
        except AccessDenied:
            result = ToolResult(tool_call_id=call_id, status="denied", retrieved_at=context.clock.now(), error=ToolError(code="ACCESS_DENIED", message="This session cannot access the requested target."))
        except TimeoutError:
            result = ToolResult(tool_call_id=call_id, status="error", retrieved_at=context.clock.now(), error=ToolError(code="TOOL_TIMEOUT", message="Data source timed out; no health conclusion is available.", retryable=True))
        except (ValidationError, ValueError):
            result = ToolResult(tool_call_id=call_id, status="error", retrieved_at=context.clock.now(), error=ToolError(code="INVALID_ARGUMENTS", message="Unknown tool or invalid arguments."))
        except (OSError, sqlite3.Error):
            result = ToolResult(tool_call_id=call_id, status="error", retrieved_at=context.clock.now(), error=ToolError(code="SOURCE_UNAVAILABLE", message="Local data source is unavailable."))
        try:
            self.repository.record_tool(context, name, result, evidence)
        except AccessDenied:
            # A forged context must not write an audit entry in another case.
            pass
        return result

    def _entries(self, kind, key, rows):
        return [(self._source(kind, row[key], row), row) for row in rows]

    def _dispatch(self, context, name, args):
        if name == "get_employee_context":
            data = self.sources.employee_context(context.employee_id)
            entries = self._entries("employee", "employee_id", [data["employee"]])
            entries += self._entries("device", "device_id", data["devices"])
            entries += self._entries("account", "account_id", data["accounts"])
            entries += self._entries("access_grant", "grant_id", data["access_grants"])
            entries += self._entries("resource", "resource_id", data["diagnostic_resources"])
            return data, entries
        if name == "search_knowledge":
            rows = self.knowledge.search(args.query, args.service_id, args.limit)
            return rows, self._entries("knowledge", "article_id", rows)
        if name == "get_runbook":
            row = self.knowledge.article(args.article_id)
            return (row, self._entries("knowledge", "article_id", [row])) if row else (None, [])
        if name == "get_service_status":
            row = self.repository.source("services", args.service_id)
            if not row or (args.region and row["region"] not in {"global", args.region}):
                return None, []
            incidents = [self.repository.source("incidents", i) for i in row["incident_ids"]]
            incidents = [i for i in incidents if i is not None]
            return {**row, "incidents": incidents}, self._entries("system_status", "service_id", [row]) + self._entries("incident", "incident_id", incidents)
        if name == "get_recent_changes":
            rows = [row for row in self.repository.sources("changes") if set(row["service_ids"]) & set(args.service_ids) and datetime.fromisoformat(row["started_at"]) >= args.since and (args.environment is None or row["environment"] == args.environment)]
            return rows, self._entries("change", "change_id", rows)
        if name == "get_diagnostic_snapshot":
            rows = self.sources.diagnostics(context.employee_id, args.service_id, args.device_id, args.resource_id)
            if args.service_id == "okta" and not args.device_id and not args.resource_id:
                accounts = [row for row in self.repository.sources("account_states") if row["employee_id"] == context.employee_id and row["service_id"] == args.service_id]
                return accounts, self._entries("account", "account_id", accounts)
            return rows, self._entries("diagnostic", "snapshot_id", rows)
        if name == "search_resolution_history":
            rows = [row for row in self.repository.sources("resolution_history") if (args.service_id is None or args.service_id in row["service_ids"]) and (args.environment is None or args.environment == row["environment"])]
            docs = [(row, " ".join([row["symptoms"], row["root_cause"], *row["actions"], row["verified_outcome"]])) for row in rows]
            matches = ranked(args.query, docs, args.limit)
            return matches, self._entries("history", "history_id", matches)
        raise ValueError("Unhandled read tool")
