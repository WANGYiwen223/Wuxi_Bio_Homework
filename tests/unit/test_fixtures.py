import copy
import json

import pytest

from scripts import demo_data
from scripts.demo_data import load_scenario, validate_all, validate_scenario
from scripts.generate_demo_data import build_fixtures


def test_all_scenarios_and_sources_validate():
    assert set(validate_all()) >= {"baseline", "account_lockout", "mixed_issues", "pipeline_maintenance"}


def test_overrides_are_isolated_and_do_not_mutate_baseline():
    _, outage = load_scenario("vpn_regional_outage")
    _, baseline = load_scenario("baseline")
    assert next(s for s in outage["services"] if s["service_id"] == "vpn")["health"] == "degraded"
    assert next(s for s in baseline["services"] if s["service_id"] == "vpn")["health"] == "healthy"
    assert len(baseline["incidents"]) == 1


def test_foreign_device_and_future_observation_are_rejected():
    scenario, original = load_scenario("baseline")
    invalid = copy.deepcopy(original)
    invalid["diagnostic_snapshots"][0]["device_id"] = "DEV-002"
    with pytest.raises(ValueError, match="ownership"):
        validate_scenario(scenario, invalid)
    invalid = copy.deepcopy(original)
    invalid["services"][0]["observed_at"] = "2027-01-01T00:00:00+08:00"
    with pytest.raises(ValueError, match="Future"):
        validate_scenario(scenario, invalid)


def test_baseline_is_healthy_and_matches_the_generator():
    config, records = load_scenario("baseline")
    assert records == build_fixtures()
    assert "employee_id" not in config
    assert all(a["status"] == "active" for a in records["account_states"])
    assert all(d["vpn_profile_revision"] == d["required_vpn_profile_revision"] for d in records["devices"])
    assert not config["generation"]["assignments"]


def test_mixed_world_has_many_people_per_problem_and_multiple_problems_per_person():
    first, records = load_scenario("mixed_issues", random_seed=42)
    assert (first, records) == load_scenario("mixed_issues", random_seed=42)
    second, changed = load_scenario("mixed_issues", random_seed=43)
    assert first["generation"]["assignments"] != second["generation"]["assignments"]
    assert records["employees"] == changed["employees"]  # Identity never changes with a problem.
    locked = {a["employee_id"] for a in records["account_states"] if a["status"] == "locked"}
    stale = {d["employee_id"] for d in records["devices"] if d["vpn_profile_revision"] < d["required_vpn_profile_revision"]}
    assert len(locked) == 4 and len(stale) == 5
    assert locked & stale and locked != stale
    assert next(s for s in records["diagnostic_snapshots"] if s["snapshot_id"] == "BUILD-001")["observations"]["last_build_status"] == "failed"


@pytest.mark.parametrize("employee", [f"EMP-{i:03}" for i in range(1, 9)])
def test_each_employee_can_receive_each_personal_problem_without_affecting_others(employee):
    for scenario, table, condition in [
        ("account_lockout", "account_states", lambda r: r["status"] == "locked"),
        ("vpn_stale_profile", "devices", lambda r: r["vpn_profile_revision"] < r["required_vpn_profile_revision"]),
    ]:
        config, records = load_scenario(scenario, [employee])
        validate_scenario(config, records)
        assert {r["employee_id"] for r in records[table] if condition(r)} == {employee}


@pytest.mark.parametrize("employees", [[], ["EMP-999"], ["EMP-001", "EMP-001"]])
def test_invalid_generation_targets_are_rejected(employees):
    with pytest.raises(ValueError):
        load_scenario("account_lockout", employees)


def test_shared_diagnostic_must_reference_an_authorized_resource_of_the_same_service():
    config, records = load_scenario("pipeline_maintenance")
    build = next(s for s in records["diagnostic_snapshots"] if s["snapshot_id"] == "BUILD-001")
    assert build["employee_id"] is None and build["device_id"] is None
    build["resource_id"] = "snowflake-prod"
    with pytest.raises(ValueError, match="scope"):
        validate_scenario(config, records)


def test_seed_records_generation_outside_sources_and_refuses_existing_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(demo_data, "ROOT", tmp_path)
    run = demo_data.seed("mixed_issues", "isolated", ["EMP-001", "EMP-002"], 7)
    manifest = json.loads((run / "manifest.json").read_text())
    assert "employee_id" not in manifest
    assert manifest["generation"]["random_seed"] == 7
    assert len(manifest["generation"]["assignments"]) == 4
    with pytest.raises(ValueError, match="Database exists"):
        demo_data.seed("mixed_issues", "isolated")
