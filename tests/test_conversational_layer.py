import json
import time
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from fastapi.testclient import TestClient

import backend.main as backend_main
from backend.services.inference_service import SatQueryInferenceService
from integration.response_generator import ResponseGenerator, build_fallback_response
from backend.services.inference_service import _reusable_results


class StubResponseClient:
    def __init__(self, answer=None, error=None, preserves_meaning=True, review_error=None):
        self.answer = answer
        self.error = error
        self.preserves_meaning = preserves_meaning
        self.review_error = review_error
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        schema = kwargs.get("format_schema", {})
        if "preserves_meaning" in schema.get("properties", {}):
            if self.review_error:
                raise self.review_error
            return json.dumps({"preserves_meaning": self.preserves_meaning})
        if self.error:
            raise self.error
        return json.dumps({"answer": self.answer})


def _analysis(execution, query="How many buildings?"):
    return {
        "status": "success",
        "run_id": "previous-run",
        "query": query,
        "execution": execution,
    }


def test_response_generator_uses_qwen_only_for_grounded_rewrite():
    client = StubResponseClient(
        "I found 19 building detections in this image, and their returned locations are marked in the viewer."
    )
    generator = ResponseGenerator(client=client)
    response = generator.generate(
        query="How many buildings?",
        status="success",
        execution={"results": [{
            "task": "BUILDING_DETECTION",
            "result": {"building_count": 19},
        }]},
    )
    assert response == {
        "answer": "I found 19 building detections in this image, and their returned locations are marked in the viewer.",
        "status": "GENERATED",
        "model": "qwen3:1.7b",
    }
    assert len(client.calls) == 2


def test_response_generator_accepts_natural_paraphrase_after_meaning_review():
    client = StubResponseClient("The model identified nineteen buildings, and their returned locations appear in the viewer.")
    response = ResponseGenerator(client=client).generate(
        "How many buildings?",
        "success",
        {"results": [{"task": "BUILDING_DETECTION", "result": {"building_count": 19, "detections": []}}]},
    )
    assert response["status"] == "GENERATED"
    assert "nineteen buildings" in response["answer"]
    assert len(client.calls) == 2
    assert "grounded_draft" in client.calls[1]["messages"][1]["content"]


def test_response_generator_rejects_unsupported_number_and_uses_real_result():
    client = StubResponseClient("I found 99 buildings in this image.", preserves_meaning=False)
    result = {"results": [{
        "task": "BUILDING_DETECTION",
        "result": {"building_count": 19},
    }]}
    response = ResponseGenerator(client=client).generate(
        "How many buildings?", "success", result
    )
    assert response["status"] == "FALLBACK"
    assert "19 building detections" in response["answer"]
    assert "99" not in response["answer"]


def test_response_generator_rejects_new_qualitative_claim_even_when_count_matches():
    client = StubResponseClient(
        "I found 19 buildings, and most are concentrated in the northeast.",
        preserves_meaning=False,
    )
    response = ResponseGenerator(client=client).generate(
        "How many buildings?",
        "success",
        {"results": [{"task": "BUILDING_DETECTION", "result": {"building_count": 19}}]},
    )
    assert response["status"] == "FALLBACK"
    assert "northeast" not in response["answer"]
    assert len(client.calls) == 2


def test_response_generator_falls_back_when_meaning_review_fails():
    client = StubResponseClient(
        "I found 19 buildings in this image.",
        review_error=TimeoutError("review timed out"),
    )
    response = ResponseGenerator(client=client).generate(
        "How many buildings?",
        "success",
        {"results": [{"task": "BUILDING_DETECTION", "result": {"building_count": 19}}]},
    )
    assert response["status"] == "FALLBACK"
    assert "19 building detections" in response["answer"]


def test_response_generator_rejects_terse_number_only_answer():
    response = ResponseGenerator(client=StubResponseClient("19")).generate(
        "How many buildings?",
        "success",
        {"results": [{
            "task": "BUILDING_DETECTION",
            "result": {"building_count": 19},
        }]},
    )
    assert response["status"] == "FALLBACK"
    assert response["answer"].startswith("I found 19 building detections")


def test_response_generator_timeout_preserves_completed_cv_result():
    client = StubResponseClient(error=TimeoutError("Ollama timed out"))
    response = ResponseGenerator(client=client).generate(
        "How many buildings?",
        "success",
        {"results": [{
            "task": "BUILDING_DETECTION",
            "result": {"building_count": 0},
        }]},
    )
    assert response["status"] == "FALLBACK"
    assert "couldn’t identify any buildings" in response["answer"]


def test_response_fallback_keeps_pixel_measurements_and_area_semantics():
    answer = build_fallback_response(
        "What percentage of the image is covered by vegetation?",
        "success",
        {"results": [{
            "task": "LAND_COVER_DETECTION",
            "result": {
                "class_pixel_counts": {"forest": 10, "agriculture": 30},
                "vegetation_pixel_summary": {
                    "forest_pixels": 10,
                    "agriculture_pixels": 30,
                    "total_vegetation_pixels": 40,
                    "vegetation_pixel_percentage": 50.0,
                },
            },
        }]},
    )
    assert "total vegetation: 40 pixels" in answer
    assert "50.00%" in answer
    assert "image-pixel" in answer
    assert "hectares" not in answer


def test_response_generator_never_calls_qwen_for_blocked_request():
    client = StubResponseClient("unused")
    response = ResponseGenerator(client=client).generate(
        "Calculate geographic area",
        "blocked",
        {"validation": {"reason": "Physical area is unsupported."}},
    )
    assert response["status"] == "DETERMINISTIC_FALLBACK"
    assert response["answer"] == "Physical area is unsupported."
    assert client.calls == []


class StubResponseGenerator:
    def __init__(self):
        self.context_resolution = None

    def generate(self, **kwargs):
        self.context_resolution = kwargs.get("context_resolution")
        return {"answer": "I reused the previous model result.", "status": "FALLBACK", "model": None}


def _fake_pipeline(task="BUILDING_COUNT", status="READY"):
    registry = SimpleNamespace(execute_tasks=Mock(return_value={
        "execution_started": True,
        "execution_status": "COMPLETED",
        "results": [],
    }))
    return SimpleNamespace(
        process_query=lambda **kwargs: {
            "m1": {"intent": "BUILDING_COUNT", "predictions": {}},
            "m2": {"subqueries": [kwargs["query"]], "combine": "SINGLE"},
            "subquery_m1_results": [],
            "task_plan": {"tasks": []},
            "routing": {"tasks": [{"task": task}]},
            "capability_validation": {"overall_status": status, "tasks": []},
        },
        registry=registry,
        m2=SimpleNamespace(model="qwen3:1.7b"),
    )


def test_followup_reuses_actual_building_result_without_running_executor(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"fixture")
    pipeline = _fake_pipeline()
    responses = StubResponseGenerator()
    service = SatQueryInferenceService(pipeline=pipeline, response_generator=responses)
    previous = _analysis({"results": [{
        "task": "BUILDING_DETECTION",
        "execution_status": "COMPLETED",
        "result": {"capability": "BUILDING_DETECTION", "building_count": 2, "detections": []},
    }]})

    result = service.run_analysis(
        "How many of them?", str(image), previous_analysis=previous
    )

    assert result["status"] == "success"
    assert result["execution"]["reused_previous_result"] is True
    assert result["execution"]["results"][0]["result"]["building_count"] == 2
    pipeline.registry.execute_tasks.assert_not_called()


def test_spatial_followup_uses_prior_detection_centers(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"fixture")
    pipeline = _fake_pipeline(task="BUILDING_RELATIONSHIP", status="BLOCKED")
    responses = StubResponseGenerator()
    service = SatQueryInferenceService(pipeline=pipeline, response_generator=responses)
    previous = _analysis({"results": [{
        "task": "BUILDING_DETECTION",
        "execution_status": "COMPLETED",
        "result": {
            "capability": "BUILDING_DETECTION",
            "building_count": 3,
            "image_width": 100,
            "image_height": 100,
            "detections": [
                {"center": [90, 10]},
                {"center": [95, 20]},
                {"center": [5, 90]},
            ],
        },
    }]})

    result = service.run_analysis(
        "Are most of them concentrated in one area?",
        str(image),
        conversation=["Assistant: I found 3 building detections."],
        previous_analysis=previous,
    )

    distribution = result["nlp"]["context_resolution"]["spatial_distribution"]
    assert result["status"] == "success"
    assert distribution["detection_count"] == 3
    assert distribution["largest_region"] == {"label": "upper-right", "count": 2}
    assert result["execution"]["results"][0]["reused"] is True
    pipeline.registry.execute_tasks.assert_not_called()


def test_explaining_previous_result_reuses_actual_result_without_executor(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"fixture")
    pipeline = _fake_pipeline(task="OUT_OF_SCOPE", status="BLOCKED")
    responses = StubResponseGenerator()
    service = SatQueryInferenceService(pipeline=pipeline, response_generator=responses)
    previous = _analysis({"results": [{
        "task": "BUILDING_DETECTION",
        "execution_status": "COMPLETED",
        "result": {"capability": "BUILDING_DETECTION", "building_count": 2, "detections": []},
    }]})

    result = service.run_analysis(
        "Can you explain the previous result?",
        str(image),
        previous_analysis=previous,
    )

    assert result["status"] == "success"
    assert result["execution"]["execution_started"] is False
    assert result["execution"]["reused_previous_result"] is True
    assert result["execution"]["results"][0]["result"]["building_count"] == 2
    assert result["nlp"]["context_resolution"]["source_run_id"] == "previous-run"
    pipeline.registry.execute_tasks.assert_not_called()


def test_explain_previous_without_context_requests_clarification(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"fixture")
    pipeline = _fake_pipeline(task="OUT_OF_SCOPE", status="BLOCKED")
    responses = StubResponseGenerator()
    service = SatQueryInferenceService(pipeline=pipeline, response_generator=responses)

    result = service.run_analysis(
        "Can you explain the previous result?",
        str(image),
    )

    assert result["status"] == "blocked"
    assert result["execution"]["execution_started"] is False
    assert result["execution"]["validation"]["reason"] == (
        "There is no earlier completed analysis in this image session to explain yet."
    )
    pipeline.registry.execute_tasks.assert_not_called()


def test_previous_result_explanation_selects_only_requested_capability(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"fixture")
    pipeline = _fake_pipeline(task="OUT_OF_SCOPE", status="BLOCKED")
    service = SatQueryInferenceService(pipeline=pipeline, response_generator=StubResponseGenerator())
    previous = _analysis({"results": [
        {"task": "BUILDING_DETECTION", "execution_status": "COMPLETED", "result": {
            "capability": "BUILDING_DETECTION", "building_count": 2, "detections": [],
        }},
        {"task": "LAND_COVER_DETECTION", "execution_status": "COMPLETED", "result": {
            "capability": "LAND_COVER_DETECTION", "class_pixel_counts": {"forest": 10},
        }},
        {"task": "FLOODED_AREA_DETECTION", "execution_status": "COMPLETED", "result": {
            "capability": "FLOODED_AREA_DETECTION", "flood_pixels": 4, "valid_pixels": 20,
        }},
    ]})

    result = service.run_analysis(
        "Can you summarize the previous flood result?", str(image), previous_analysis=previous
    )

    assert result["status"] == "success"
    assert [row["task"] for row in result["execution"]["results"]] == ["FLOODED_AREA_DETECTION"]
    pipeline.registry.execute_tasks.assert_not_called()


def test_generic_previous_result_explanation_keeps_legitimate_multi_capability_result(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"fixture")
    pipeline = _fake_pipeline(task="OUT_OF_SCOPE", status="BLOCKED")
    service = SatQueryInferenceService(pipeline=pipeline, response_generator=StubResponseGenerator())
    previous = _analysis({"results": [
        {"task": "BUILDING_DETECTION", "execution_status": "COMPLETED", "result": {
            "capability": "BUILDING_DETECTION", "building_count": 2, "detections": [],
        }},
        {"task": "LAND_COVER_DETECTION", "execution_status": "COMPLETED", "result": {
            "capability": "LAND_COVER_DETECTION", "class_pixel_counts": {"forest": 10},
        }},
    ]})

    result = service.run_analysis(
        "Can you explain the previous result?", str(image), previous_analysis=previous
    )

    assert result["status"] == "success"
    assert [row["task"] for row in result["execution"]["results"]] == [
        "BUILDING_DETECTION", "LAND_COVER_DETECTION",
    ]


def test_previous_result_explanation_does_not_substitute_an_unrelated_capability(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"fixture")
    pipeline = _fake_pipeline(task="OUT_OF_SCOPE", status="BLOCKED")
    service = SatQueryInferenceService(pipeline=pipeline, response_generator=StubResponseGenerator())
    previous = _analysis({"results": [{
        "task": "BUILDING_DETECTION", "execution_status": "COMPLETED", "result": {
            "capability": "BUILDING_DETECTION", "building_count": 2, "detections": [],
        },
    }]})

    result = service.run_analysis(
        "Explain the previous flood result.", str(image), previous_analysis=previous
    )

    assert result["status"] == "blocked"
    assert result["nlp"]["context_resolution"]["status"] == "CAPABILITY_UNAVAILABLE"
    assert "requested capability" in result["execution"]["validation"]["reason"]
    pipeline.registry.execute_tasks.assert_not_called()


def test_reuse_matches_task_specific_output_and_preserves_source_capability():
    previous = _analysis({"results": [{
        "task": "BUILDING_DETECTION", "execution_status": "COMPLETED", "result": {
            "capability": "BUILDING_DETECTION", "building_count": 2, "detections": [],
        },
    }]})

    reused = _reusable_results([{"task": "BUILDING_COUNT"}], previous)

    assert reused[0]["task"] == "BUILDING_COUNT"
    assert reused[0]["result"]["capability"] == "BUILDING_COUNT"
    assert reused[0]["result"]["source_capability"] == "BUILDING_DETECTION"


def test_reuse_rejects_unrelated_capability_and_duplicate_consumption():
    building = {"task": "BUILDING_DETECTION", "execution_status": "COMPLETED", "result": {
        "capability": "BUILDING_DETECTION", "building_count": 2, "detections": [],
    }}
    assert _reusable_results([{"task": "FLOODED_AREA_DETECTION"}], _analysis({"results": [building]})) is None
    assert _reusable_results(
        [{"task": "BUILDING_COUNT"}, {"task": "BUILDING_LOCATE"}],
        _analysis({"results": [building]}),
    ) is None


def test_backend_session_isolated_and_invalidated_on_image_changes():
    first_session = f"session-{uuid4()}"
    second_session = f"session-{uuid4()}"
    first_image, second_image, after_one, after_two = [str(uuid4()) for _ in range(4)]
    previous = _analysis({"results": [{
        "task": "BUILDING_CHANGE",
        "execution_status": "COMPLETED",
        "result": {"changed_pixels_at_model_resolution": 12},
    }]})
    backend_main._conversation_sessions[first_session] = {
        "image_id": first_image,
        "second_image_id": after_one,
        "turns": [{"query": "Compare", "assistant_response": "There were changes.", "uses_comparison": True}],
        "last_analysis": previous,
        "updated_at": time.monotonic(),
    }
    try:
        conversation, cached = backend_main._conversation_snapshot(first_session, first_image, after_one)
        assert conversation == ["User: Compare", "Assistant: There were changes."]
        assert cached["run_id"] == "previous-run"

        conversation, cached = backend_main._conversation_snapshot(first_session, first_image, after_two)
        assert conversation == []
        assert cached is None

        conversation, cached = backend_main._conversation_snapshot(first_session, second_image, after_two)
        assert conversation == []
        assert cached is None

        other_conversation, other_cached = backend_main._conversation_snapshot(second_session, first_image, after_one)
        assert other_conversation == []
        assert other_cached is None
    finally:
        backend_main._conversation_sessions.pop(first_session, None)
        backend_main._conversation_sessions.pop(second_session, None)


def test_query_api_supplies_recent_turns_and_resets_when_primary_changes(monkeypatch):
    client_session = f"session-{uuid4()}"
    first_image, replacement_image = str(uuid4()), str(uuid4())
    received = []
    monkeypatch.setattr(backend_main, "find_uploaded_image", lambda _image_id: "uploaded-image")

    def fake_execute(image_id, query, second_image_id=None, conversation=None, previous_analysis=None):
        received.append({
            "image_id": image_id,
            "query": query,
            "conversation": list(conversation or []),
            "previous_analysis": previous_analysis,
        })
        return {
            "status": "success",
            "run_id": str(uuid4()),
            "query": query,
            "assistant_response": "I checked the current image.",
            "execution": {"results": []},
        }

    monkeypatch.setattr(backend_main, "execute_analysis", fake_execute)
    client = TestClient(backend_main.app)
    try:
        first = client.post("/api/query", json={
            "query": "Find buildings.", "imageId": first_image, "sessionId": client_session,
        })
        second = client.post("/api/query", json={
            "query": "How many of them?", "imageId": first_image, "sessionId": client_session,
        })
        replaced = client.post("/api/query", json={
            "query": "What about the buildings?", "imageId": replacement_image, "sessionId": client_session,
        })

        assert first.status_code == second.status_code == replaced.status_code == 200
        assert first.json()["session_id"] == client_session
        assert received[1]["conversation"] == [
            "User: Find buildings.",
            "Assistant: I checked the current image.",
        ]
        assert received[1]["previous_analysis"]["status"] == "success"
        assert received[2]["conversation"] == []
        assert received[2]["previous_analysis"] is None
    finally:
        backend_main._conversation_sessions.pop(client_session, None)
