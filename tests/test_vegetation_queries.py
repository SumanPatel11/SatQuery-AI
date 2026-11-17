import json

import pytest

from backend.services.inference_service import _add_vegetation_pixel_summary
from nlp.capability_registry import CapabilityRegistry
from nlp.query_router import HybridQueryRouter
from nlp.task_planner import TaskPlanner


class PlannerClient:
    def __init__(self, task):
        self.task = task

    def chat(self, **kwargs):
        return json.dumps(self.task)


def _planned(query, operation="DETECT", target="vegetation", intent="LAND_COVER_ANALYSIS"):
    planner = TaskPlanner(client=PlannerClient({
        "operation": operation,
        "target": target,
        "region": "forest",
        "spatial_relation": "agricultural_regions",
    }))
    return planner.plan(
        original_query=query,
        m1_result={"intent": intent},
        m2_result={"subqueries": [query]},
        subquery_m1_results=[{"intent": intent, "predictions": {}}],
    )


@pytest.mark.parametrize("query,operation", [
    ("Analyze vegetation cover.", "DETECT"),
    ("Detect vegetation.", "DETECT"),
    ("How much vegetation is present?", "COUNT"),
    ("Find forest and agricultural regions.", "DETECT"),
    ("Report forest pixel count.", "COUNT"),
    ("Report agriculture pixel count.", "COUNT"),
    ("What percentage of this image is covered by vegetation?", "DETECT"),
    ("Calculate vegetation pixel coverage.", "DETECT"),
])
def test_vegetation_queries_plan_to_loveda(query, operation):
    task = _planned(query, operation="AREA" if "percentage" in query else "DETECT") ["tasks"][0]
    assert task["operation"] == operation
    assert task["target"] == "land_cover"
    assert task["region"] == "none"
    assert task["spatial_relation"] == "none"


def test_physical_area_request_remains_unsupported():
    task = _planned(
        "Calculate the geographic area of forest in hectares.",
        operation="AREA",
    )["tasks"][0]
    assert task["operation"] == "AREA"
    assert task["target"] == "land_cover"

    router = HybridQueryRouter()
    routed = router.route(
        m1_result={"intent": "LAND_COVER_ANALYSIS"},
        m2_result={"subqueries": ["Calculate the geographic area of forest in hectares."]},
        subquery_m1_results=[{"intent": "LAND_COVER_ANALYSIS"}],
        task_plan={"tasks": [task]},
    )
    assert routed["tasks"][0]["task"] == "LAND_COVER_AREA_UNSUPPORTED"
    registry = CapabilityRegistry()
    validation = registry.validate_tasks(routed["tasks"])
    assert validation["overall_status"] == "BLOCKED"
    assert "physical land-cover area" in validation["tasks"][0]["reason"]

    # Preserve physical-area semantics even if M2 drops the unit wording from
    # its decomposed land-cover subquery.
    dropped_unit_task = TaskPlanner._normalize_land_cover_task(
        "Find forest regions.",
        {"operation": "DETECT", "target": "forest", "region": "none", "spatial_relation": "none"},
        "LAND_COVER_ANALYSIS",
        "Calculate the geographic area of forest in hectares.",
    )
    assert dropped_unit_task["operation"] == "AREA"

    ambiguous_area_task = TaskPlanner._normalize_land_cover_task(
        "Calculate area covered by vegetation in the image.",
        {"operation": "AREA", "target": "vegetation", "region": "none", "spatial_relation": "none"},
        "LAND_COVER_ANALYSIS",
        "Calculate vegetation area.",
    )
    assert ambiguous_area_task["operation"] == "AREA"


@pytest.mark.parametrize("query", [
    "Analyze vegetation cover.",
    "What percentage of this image is covered by vegetation?",
    "Report forest pixel count.",
    "Report agriculture pixel count.",
    "Calculate vegetation pixel counts.",
])
def test_supported_land_cover_tasks_validate_against_real_capability_name(tmp_path, query):
    task = _planned(query)["tasks"][0]
    routed = HybridQueryRouter().route(
        m1_result={"intent": "LAND_COVER_ANALYSIS"},
        m2_result={"subqueries": [query]},
        subquery_m1_results=[{"intent": "LAND_COVER_ANALYSIS"}],
        task_plan={"tasks": [task]},
    )
    assert [item["task"] for item in routed["tasks"]] == ["LAND_COVER_DETECTION"]

    implementation = tmp_path / "land_cover.py"
    checkpoint = tmp_path / "best.pt"
    implementation.write_text("source", encoding="utf-8")
    checkpoint.write_bytes(b"checkpoint marker")
    registry = CapabilityRegistry()
    registry.register("LAND_COVER_DETECTION", lambda **kwargs: {}, str(implementation), [str(checkpoint)])
    validation = registry.validate_tasks(routed["tasks"])
    assert validation["overall_status"] == "READY"
    assert validation["ready_tasks"] == 1


def test_decomposed_forest_and_agriculture_subqueries_use_one_capability():
    queries = ["Find forest regions.", "Find agricultural regions."]
    planner = TaskPlanner(client=PlannerClient({
        "operation": "DETECT",
        "target": "flooded_area",
        "region": "forest",
        "spatial_relation": "agricultural_regions",
    }))
    plan = planner.plan(
        original_query="Find forest and agricultural regions.",
        m1_result={"intent": "LAND_COVER_ANALYSIS"},
        m2_result={"subqueries": queries},
        subquery_m1_results=[
            {"intent": "LAND_COVER_ANALYSIS"},
            {"intent": "OUT_OF_SCOPE"},
        ],
    )
    assert all(task["target"] == "land_cover" for task in plan["tasks"])
    routed = HybridQueryRouter().route(
        m1_result={"intent": "LAND_COVER_ANALYSIS"},
        m2_result={"subqueries": queries},
        subquery_m1_results=[{"intent": "LAND_COVER_ANALYSIS"}, {"intent": "OUT_OF_SCOPE"}],
        task_plan=plan,
    )
    assert len(routed["tasks"]) == 1
    assert routed["tasks"][0]["task"] == "LAND_COVER_DETECTION"
    assert len(routed["tasks"][0]["source_subqueries"]) == 2


def test_vegetation_pixel_statistics_derive_from_same_real_class_counts():
    execution = {"results": [{
        "task": "LAND_COVER_DETECTION",
        "result": {
            "image_width": 4,
            "image_height": 2,
            "class_pixel_counts": {
                    "background": 1, "building": 1, "road": 1, "water": 1,
                    "barren": 0, "forest": 3, "agriculture": 1,
            },
        },
    }]}
    _add_vegetation_pixel_summary(execution)
    summary = execution["results"][0]["result"]["vegetation_pixel_summary"]
    assert summary["forest_pixels"] == 3
    assert summary["agriculture_pixels"] == 1
    assert summary["total_vegetation_pixels"] == 4
    assert summary["valid_image_pixels"] == 8
    assert summary["vegetation_pixel_fraction"] == 0.5
    assert summary["vegetation_pixel_percentage"] == 50.0
    assert summary["measurement"] == "image_pixels"


def test_inconsistent_class_counts_do_not_publish_percentage():
    execution = {"results": [{
        "task": "LAND_COVER_DETECTION",
        "result": {
            "image_width": 4, "image_height": 2,
            "class_pixel_counts": {"forest": 2, "agriculture": 1},
        },
    }]}
    _add_vegetation_pixel_summary(execution)
    assert "vegetation_pixel_summary" not in execution["results"][0]["result"]
