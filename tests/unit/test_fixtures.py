import copy

import pytest

from scripts.demo_data import load_scenario, validate_all, validate_scenario


def test_all_scenarios_and_sources_validate():
    assert len(validate_all()) == 7


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
