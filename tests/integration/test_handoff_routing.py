"""Handoff routing regression tests for the structured issue-category mechanism (P2 fix).

The model declares a category for the employee's actual problem; the backend maps it to a
queue (ISSUE_GROUPS) and a phrase-level safety net over employee text can only escalate to
security. Incidental evidence and keyword substrings must never reroute — that was the P2
misrouting mechanism proven by the 2026-10-14 probe run (probes/FINDINGS.md). Messages here
reuse the probes' own texts so each test names the case it pins.
"""

import json
import sqlite3

from test_policy_approvals import setup

import pytest

from helpdesk.escalation.service import HandoffService


def _persisted_package(repo, handoff_id):
    with sqlite3.connect(repo.path) as db:
        row = db.execute("SELECT payload FROM handoffs WHERE record_id=?", (handoff_id,)).fetchone()
    return json.loads(row[0])


def routed(seeded_db, tmp_path, messages, category=None, evidence_services=(), employee="EMP-002"):
    """Create a baseline case, seed employee messages plus incidentally retrieved
    get_service_status evidence, escalate, and read the persisted handoff package."""
    repo, ctx, _, _, tools = setup(seeded_db, tmp_path, "baseline", employee)
    for text in messages:
        repo.append_message(ctx, "employee", text)
    for service_id in evidence_services:
        assert tools.call(ctx, "get_service_status", {"service_id": service_id}).status == "success"
    result = HandoffService(repo).create(ctx, "Investigation exceeds IT authority", category=category)
    assert result["status"] == "queued"
    return _persisted_package(repo, result["handoff_id"])


# --- Probe-proven misroutes: declared category now rules, incidental evidence is inert ---

def test_stolen_laptop_is_a_security_incident(seeded_db, tmp_path):  # probe C5
    package = routed(
        seeded_db, tmp_path,
        ["My company laptop was stolen from my car an hour ago. It had client files on it and I think it was still logged in."],
        category="security_incident", evidence_services=["tableau"], employee="EMP-004")
    assert package["support_group"] == "security" and package["routing_basis"] == "model_declared"


def test_vpn_disconnect_loop_routes_network(seeded_db, tmp_path):  # probe D2
    package = routed(
        seeded_db, tmp_path,
        ["My VPN keeps disconnecting every 12 minutes on my assigned remote laptop."],
        category="network_connectivity", evidence_services=["jenkins", "vpn"], employee="EMP-004")
    assert package["support_group"] == "network"


def test_printer_hardware_routes_helpdesk(seeded_db, tmp_path):  # probe C3
    package = routed(
        seeded_db, tmp_path,
        ["The printer on the 3rd floor won't print anything this morning. It just blinks orange."],
        category="peripheral_hardware", evidence_services=["vpn"], employee="EMP-006")
    assert package["support_group"] == "helpdesk"


def test_software_install_routes_helpdesk(seeded_db, tmp_path):  # probe C8
    package = routed(
        seeded_db, tmp_path,
        ["Can you install Tableau Desktop on my laptop? I need it to build a report this week."],
        category="software_install", evidence_services=["tableau"], employee="EMP-002")
    assert package["support_group"] == "helpdesk"


def test_manager_access_inquiry_routes_helpdesk(seeded_db, tmp_path):  # probe C6
    package = routed(
        seeded_db, tmp_path,
        ["Did my new hire Alex Chen get his Snowflake production access yet? Can you check the status of his request?"],
        category="access_inquiry", evidence_services=["jenkins"], employee="EMP-005")
    assert package["support_group"] == "helpdesk"


def test_negated_compromise_mention_keeps_declared_category(seeded_db, tmp_path):  # B7 class
    package = routed(
        seeded_db, tmp_path,
        ["I can't log into Okta. I don't think my account was compromised, the page just says something went wrong."],
        category="account_access", employee="EMP-003")
    assert package["support_group"] == "helpdesk"


# --- Category-to-queue mapping for the queues the model can reach ---

def test_phishing_report_routes_security(seeded_db, tmp_path):  # probe B5
    package = routed(
        seeded_db, tmp_path,
        ["I got an email that looked like it was from IT, clicked the link, and typed my Okta password into the page."],
        category="security_incident", employee="EMP-002")
    assert package["support_group"] == "security"


def test_pipeline_infrastructure_routes_sre(seeded_db, tmp_path):  # probe A5
    package = routed(
        seeded_db, tmp_path,
        ["Since the IT maintenance window last Friday, our team's automated data pipeline has been failing. The Jenkins jobs time out."],
        category="pipeline_infrastructure", evidence_services=["jenkins"], employee="EMP-004")
    assert package["support_group"] == "sre"


def test_missing_category_falls_back_to_helpdesk_triage(seeded_db, tmp_path):
    package = routed(
        seeded_db, tmp_path,
        ["I can't log into Okta, the page just fails."],
        employee="EMP-003")
    assert package["support_group"] == "helpdesk" and package["routing_basis"] == "internal_fallback"


# --- Safety net: upgrades unflagged security signals, respects negation ---

def test_safety_net_upgrades_unflagged_theft_to_security(seeded_db, tmp_path):
    package = routed(
        seeded_db, tmp_path,
        ["My company laptop was stolen from my car an hour ago. It had client files on it and I think it was still logged in."],
        category="account_access", employee="EMP-004")
    assert package["support_group"] == "security" and package["routing_basis"] == "backend_override"


def test_safety_net_ignores_negated_mentions(seeded_db, tmp_path):
    package = routed(
        seeded_db, tmp_path,
        ["I did not click the link and never typed my password anywhere. There is no suspicious login on my account."],
        category="account_access", employee="EMP-003")
    assert package["support_group"] == "helpdesk"


def test_unknown_category_is_rejected(seeded_db, tmp_path):
    repo, ctx, _, _, _ = setup(seeded_db, tmp_path, "baseline", "EMP-002")
    repo.append_message(ctx, "employee", "printer is broken")
    with pytest.raises(ValueError):
        HandoffService(repo).create(ctx, "reason", category="security")  # queue name, not a category
