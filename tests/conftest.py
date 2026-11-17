"""Keep local-checkpoint inference smoke tests out of normal unit runs."""

import os

import pytest


def pytest_collection_modifyitems(items):
    if os.environ.get("SATQUERY_RUN_REAL_CV_SMOKE") == "1":
        return

    optional_smoke = "test_land_cover_registry.py::LandCoverRegistryTests::test_executor_output_contract"
    skip_smoke = pytest.mark.skip(
        reason="Optional real-model smoke test; set SATQUERY_RUN_REAL_CV_SMOKE=1 to enable"
    )
    for item in items:
        if optional_smoke in item.nodeid:
            item.add_marker(skip_smoke)
