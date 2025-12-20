import pytest

from custom_components.sensor_proxy.glob_helpers import matches_patterns


def test_matches_no_patterns():
    # No include/exclude -> accept
    assert matches_patterns("foo", None, None) is True
    # Empty lists are treated as no-op
    assert matches_patterns("foo", [], []) is True


def test_matches_include():
    assert matches_patterns("refoss_3_power", ["*_power", "*_energy"], None)
    assert not matches_patterns("refoss_3_power", ["*_energy"], None)


def test_matches_exclude():
    assert not matches_patterns("refoss_3_energy_daily", None, ["*_daily"])
    assert matches_patterns("refoss_3_energy", None, ["*_daily"])


def test_include_and_exclude():
    include = ["*_energy", "*_power"]
    exclude = ["*_energy_daily"]
    assert not matches_patterns("refoss_3_energy_daily", include, exclude)
    assert matches_patterns("refoss_3_power", include, exclude)
