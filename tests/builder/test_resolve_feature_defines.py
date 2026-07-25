"""Tests for builder label to define resolution."""
from unittest.mock import Mock

from builder.builder import resolve_feature_defines


def _option(label, define):
    opt = Mock()
    opt.label = label
    opt.define = define
    return opt


def test_resolve_feature_defines_maps_labels():
    features = [
        _option("HAL_LOGGING_ENABLED", "HAL_LOGGING_ENABLED_DEFINE"),
        _option("HAL_WITH_EKF3", "HAL_WITH_EKF3_DEFINE"),
    ]

    enabled, disabled, all_defines, unknown = resolve_feature_defines(
        ["HAL_LOGGING_ENABLED"],
        features,
    )

    assert enabled == {"HAL_LOGGING_ENABLED_DEFINE"}
    assert disabled == {"HAL_WITH_EKF3_DEFINE"}
    assert all_defines == {
        "HAL_LOGGING_ENABLED_DEFINE",
        "HAL_WITH_EKF3_DEFINE",
    }
    assert unknown == set()


def test_resolve_feature_defines_returns_unknown_labels():
    features = [_option("HAL_LOGGING_ENABLED", "HAL_LOGGING_ENABLED_DEFINE")]

    enabled, disabled, all_defines, unknown = resolve_feature_defines(
        ["COMPLETELY_UNKNOWN_FEATURE"],
        features,
    )

    assert enabled == set()
    assert disabled == all_defines == {"HAL_LOGGING_ENABLED_DEFINE"}
    assert unknown == {"COMPLETELY_UNKNOWN_FEATURE"}


def test_resolve_feature_defines_empty_selection_disables_all():
    features = [_option("HAL_LOGGING_ENABLED", "HAL_LOGGING_ENABLED_DEFINE")]

    enabled, disabled, all_defines, unknown = resolve_feature_defines(
        [], features
    )

    assert enabled == set()
    assert disabled == all_defines == {"HAL_LOGGING_ENABLED_DEFINE"}
    assert unknown == set()
