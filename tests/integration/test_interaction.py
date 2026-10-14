"""Progress is observable before completion; citations never expose storage IDs."""

from concurrent.futures import ThreadPoolExecutor
import logging
import threading

import pytest

from helpdesk.models.client import ModelReply
from helpdesk.observability.presentation import present_answer, source_catalog
from test_api import application, login
from test_workflow import ScriptModel, setup, tool


def test_response_failure_is_visible_in_api_activity_and_diagnostics(application):
    client, runtime = application
    runtime.agent.model = ScriptModel([ModelReply(finish_reason="length", output_tokens=4096, reasoning_tokens=4096), ModelReply()])
    headers = login(client)
    case_id = client.post('/cases', headers=headers).json()['case_id']
    path = f'/cases/{case_id}'
    response = client.post(path + '/messages', json={'text': 'Cannot sign into Okta.'}, headers=headers)
    assert response.status_code == 200
    assert response.json()['failure'] == 'model_empty_response'
    assert response.json()['case']['status'] == 'escalated'
    activity = client.get(path + '/activity', headers=headers).json()['events']
    assert len([e for e in activity if e['event'] == 'model_response_retry']) == 1
    assert all(e['status'] == 'error' for e in activity if e['event'] == 'model_call')
    diagnostics = client.get(path + '/diagnostics', headers=headers).json()['events']
    calls = [e for e in diagnostics if e['event'] == 'model_call']
    assert calls[0]['finish_reason'] == 'length' and calls[0]['reasoning_tokens'] == 4096
    assert calls[1]['max_output_tokens'] == 8192
    assert client.post(path + '/messages', json={'text': 'I already told you.'}, headers=headers).status_code == 409


def test_progress_is_visible_while_model_is_blocked_and_scoped(application, caplog):
    client, runtime = application
    entered, release = threading.Event(), threading.Event()

    class SlowModel:
        def respond(self, messages, schemas, *, max_output_tokens=None):
            entered.set()
            assert release.wait(10)
            return ModelReply(text="Which application fails?")

    runtime.agent.model = SlowModel()
    headers = login(client)
    case_id = client.post('/cases', headers=headers).json()['case_id']
    path = f'/cases/{case_id}'
    with caplog.at_level(logging.INFO, logger='helpdesk.events'), ThreadPoolExecutor() as pool:
        pending = pool.submit(client.post, path + '/messages', headers=headers, json={'text':'password=private-secret My login fails'})
        try:
            assert entered.wait(10)
            progress = client.get(path + '/activity', headers=headers).json()
            assert [e['event'] for e in progress['events']] == ['turn_started', 'model_started']
            assert progress['events'][-1]['status'] == 'running'
            assert not pending.done()
            assert client.get(path + '/activity', headers=login(client, 'EMP-001')).status_code == 403
            assert client.get(path + '/diagnostics', headers=login(client)).status_code == 403
            assert client.get(path + '/activity?after=-1', headers=headers).status_code == 422
        finally:
            release.set()
        assert pending.result().status_code == 200
        following = client.get(path + '/activity', headers=headers, params={'after':progress['cursor']}).json()
        assert following['events'][-1]['event'] == 'turn_completed'
        assert all(e['sequence'] > progress['cursor'] for e in following['events'])
        diagnostics = client.get(path + '/diagnostics', headers=headers).json()['events']
        assert diagnostics[-1]['model_calls'] == 1
        assert diagnostics[-1]['duration_ms'] >= 0
        assert diagnostics[0]['recorded_at'] != diagnostics[0]['created_at']
    assert 'model_started' in caplog.text and 'turn_completed' in caplog.text
    assert 'private-secret' not in caplog.text and 'My login fails' not in caplog.text


def test_citations_match_stored_sources_in_response_and_history(application):
    client, runtime = application
    headers = login(client)
    case_id = client.post('/cases', headers=headers).json()['case_id']
    ctx = runtime.context(headers['Authorization'][7:], case_id)
    result = runtime.reads.call(ctx, 'get_service_status', {'service_id':'vpn'})
    evidence_id = result.evidence_ids[0]
    runtime.agent.model = ScriptModel([ModelReply(text=f'VPN is healthy [[{evidence_id}]]. Unknown: EVID-deadbeef.')])
    response = client.post(f'/cases/{case_id}/messages', headers=headers, json={'text':'Check VPN'}).json()
    assert response['message'] == 'VPN is healthy [1]. Unknown: [source unavailable].'
    assert response['citations'][0]['title'] == 'VPN · Service health'
    snapshot = client.get(f'/cases/{case_id}', headers=headers).json()
    assert snapshot['messages'][-1]['text'] == response['message']
    assert snapshot['messages'][-1]['citations'] == response['citations']
    assert snapshot['sources'][0]['number'] == 1
    assert snapshot['evidence'][0]['evidence_id'] == evidence_id
    # The original reference survives for audits and model dialogue.
    assert evidence_id in runtime.repository.messages(ctx)[-1].text


def test_repeated_source_snapshot_reuses_number_without_losing_audit_ids(application):
    _, runtime = application
    repo = runtime.repository
    session = repo.create_demo_session('EMP-003')
    case = repo.create_case(session, runtime.clock)
    ctx = runtime.context(session, case.case_id)
    first = runtime.reads.call(ctx, 'get_service_status', {'service_id':'vpn'})
    second = runtime.reads.call(ctx, 'get_service_status', {'service_id':'vpn'})
    evidence = repo.evidence(ctx)
    sources, refs = source_catalog(evidence)
    assert len(sources) == 1 and first.evidence_ids != second.evidence_ids
    assert refs[first.evidence_ids[0]] == refs[second.evidence_ids[0]] == 1
    assert present_answer(f'`{first.evidence_ids[0]}` and [{second.evidence_ids[0]}]', evidence)['text'] == '[1] and [1]'


def test_invalid_and_skipped_tools_have_terminal_events(seeded_db, tmp_path):
    from helpdesk.models.client import ToolCall
    import json
    reply = ModelReply(calls=[
        ToolCall(call_id='bad', name='get_employee_context', arguments='{'),
        ToolCall(call_id='finish', name='finish_turn', arguments=json.dumps({'kind':'clarify', 'message':'Which service?'})),
        ToolCall(call_id='skipped', name='get_employee_context', arguments='{}'),
    ])
    repo, ctx, agent = setup(seeded_db, tmp_path, ScriptModel([reply]))
    try:
        agent.turn(ctx, 'Help')
        events = repo.events(ctx)
        completed = {e['call_id']:e for e in events if e['event'] == 'tool_completed'}
        assert completed['bad']['error_code'] == 'INVALID_ARGUMENTS'
        assert completed['skipped']['status'] == 'skipped'
        assert not repo.evidence(ctx)
    finally:
        agent.close()


def test_unexpected_failure_is_not_left_running(seeded_db, tmp_path):
    repo, ctx, agent = setup(seeded_db, tmp_path, ScriptModel([RuntimeError('private-error-body')]))
    try:
        with pytest.raises(RuntimeError):
            agent.turn(ctx, 'Help')
        event = repo.events(ctx)[-1]
        assert event['event'] == 'turn_failed' and event['error_type'] == 'RuntimeError'
        assert 'private-error-body' not in str(repo.events(ctx))
    finally:
        agent.close()


def test_rolled_back_audit_events_do_not_reach_application_log(application, caplog):
    _, runtime = application
    with caplog.at_level(logging.INFO, logger='helpdesk.events'):
        with pytest.raises(RuntimeError):
            with runtime.repository.transaction() as db:
                runtime.repository.audit(db, {'event':'must_not_be_logged'})
                raise RuntimeError('rollback')
    assert 'must_not_be_logged' not in caplog.text
