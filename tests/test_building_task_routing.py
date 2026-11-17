from nlp.capability_registry import CapabilityRegistry
from nlp.query_router import HybridQueryRouter


def test_building_count_and_locate_share_one_detector_execution(tmp_path):
    subqueries = [
        "How many buildings can you identify?",
        "Locate the buildings and show their boxes.",
    ]
    planned_tasks = [
        {
            "source_subquery": subqueries[0],
            "operation": "COUNT",
            "target": "building",
            "region": "none",
            "spatial_relation": "none",
        },
        {
            "source_subquery": subqueries[1],
            "operation": "LOCATE",
            "target": "building",
            "region": "none",
            "spatial_relation": "none",
        },
    ]

    routed = HybridQueryRouter().route(
        m1_result={"intent": "BUILDING_DETECTION"},
        m2_result={"subqueries": subqueries},
        subquery_m1_results=[
            {"intent": "BUILDING_COUNT"},
            {"intent": "BUILDING_DETECTION"},
        ],
        task_plan={"tasks": planned_tasks},
    )

    assert routed["execution_mode"] == "SINGLE_TASK"
    assert len(routed["tasks"]) == 1
    task = routed["tasks"][0]
    assert task["task"] == "BUILDING_DETECTION"
    assert task["operation"] == "DETECT"
    assert task["source_subqueries"] == subqueries
    assert task["requested_operations"] == ["COUNT", "LOCATE"]

    image = tmp_path / "input.png"
    implementation = tmp_path / "building.py"
    checkpoint = tmp_path / "best.pt"
    output_dir = tmp_path / "outputs"
    image.write_bytes(b"input")
    implementation.write_text("implementation", encoding="utf-8")
    checkpoint.write_bytes(b"checkpoint marker")

    calls = []

    def detector(**kwargs):
        calls.append(kwargs)
        return {
            "capability": "BUILDING_DETECTION",
            "building_count": 2,
            "detections": [],
        }

    registry = CapabilityRegistry()
    registry.register(
        "BUILDING_DETECTION",
        detector,
        str(implementation),
        [str(checkpoint)],
    )
    execution = registry.execute_tasks(
        [task], str(image), str(output_dir)
    )

    assert execution["execution_status"] == "COMPLETED"
    assert len(execution["results"]) == 1
    assert execution["results"][0]["result"]["building_count"] == 2
    assert len(calls) == 1
