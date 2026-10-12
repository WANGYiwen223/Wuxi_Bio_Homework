from datetime import datetime

import pytest

from helpdesk.bootstrap.context import DemoClock, ToolContext
from helpdesk.domain.contracts import Case
from helpdesk.domain.lifecycle import transition
from helpdesk.storage.repository import AccessDenied, Repository, RevisionConflict


def setup(seeded_db):
    path, scenario = seeded_db()
    repo = Repository(path)
    clock = DemoClock(datetime.fromisoformat(scenario["clock"]))
    session = repo.create_demo_session("EMP-003")
    case = repo.create_case(session, clock)
    return repo, clock, repo.context(session, case.case_id, clock)


def test_restart_preserves_messages_case_facts_and_status(seeded_db):
    repo, clock, ctx = setup(seeded_db)
    repo.append_message(ctx, "employee", "Okta login still fails")
    repo.append_message(ctx, "assistant", "Is MFA available?")
    saved = repo.save_case(ctx, transition(repo.get_case(ctx), "awaiting_employee", clock.now(), facts={"service": "okta", "password_reset_tried": True}))
    reopened = Repository(repo.path)
    assert reopened.get_case(ctx) == saved
    assert [m.role for m in reopened.messages(ctx)] == ["employee", "assistant"]


def test_cross_employee_and_forged_context_access_is_denied(seeded_db):
    repo, clock, ctx = setup(seeded_db)
    other = repo.create_demo_session("EMP-001")
    with pytest.raises(AccessDenied):
        repo.context(other, ctx.case_id, clock)
    forged = ToolContext(ctx.session_id, "EMP-001", ctx.case_id, True, clock)
    with pytest.raises(AccessDenied):
        repo.get_case(forged)
    altered = Case(**{**repo.get_case(ctx).model_dump(), "employee_id": "EMP-001"})
    with pytest.raises(AccessDenied):
        repo.save_case(ctx, altered)


def test_concurrent_updates_require_reload(seeded_db):
    repo, clock, ctx = setup(seeded_db)
    old = repo.get_case(ctx)
    repo.save_case(ctx, transition(old, "awaiting_employee", clock.now()))
    with pytest.raises(RevisionConflict):
        repo.save_case(ctx, transition(old, "awaiting_approval", clock.now()))
