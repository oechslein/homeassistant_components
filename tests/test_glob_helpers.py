from custom_components.sensor_proxy.glob_helpers import (
    extract_domain_from_glob,
    matches_patterns,
)


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


def test_include_as_string():
    assert matches_patterns("refoss_3_power", "*_power", None)
    assert not matches_patterns("refoss_3_power", "*_energy", None)


def test_invalid_patterns_are_safe():
    # Passing a non-iterable for patterns should not raise; treated as non-match
    assert matches_patterns("refoss_3_power", None, None) is True
    assert matches_patterns("refoss_3_power", 123, None) is False


def test_extract_domain_from_glob():
    # Valid patterns with explicit domain
    assert extract_domain_from_glob("sensor.original_*") == "sensor"
    assert extract_domain_from_glob("light.bedroom_*") == "light"
    assert extract_domain_from_glob("binary_sensor.*") == "binary_sensor"
    
    # Invalid patterns (wildcarded domain)
    assert extract_domain_from_glob("*.original") is None
    assert extract_domain_from_glob("*.*") is None
    assert extract_domain_from_glob("sen*.something") is None
    
    # Edge cases
    assert extract_domain_from_glob("") is None
    assert extract_domain_from_glob("no_dot_here") is None
    assert extract_domain_from_glob("sensor.") == "sensor"
