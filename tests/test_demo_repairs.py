from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import numpy as np
import rasterio
from fastapi.testclient import TestClient
from PIL import Image
from rasterio.transform import from_origin

import backend.main as backend_main
from backend.services.inference_service import (
    SatQueryInferenceService,
    _flood_input_error,
)


def _write_raster(path: Path, bands: int, width: int = 224, height: int = 224):
    profile = {
        "driver": "GTiff",
        "width": width,
        "height": height,
        "count": bands,
        "dtype": "float32",
        "transform": from_origin(0, 1, 1, 1),
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(np.zeros((bands, height, width), dtype=np.float32))
    return path


def test_flood_input_validation_rejects_rgb_and_non_geotiff(tmp_path):
    rgb_raster = _write_raster(tmp_path / "rgb.tif", bands=3)
    assert "exactly 2 SAR bands" in _flood_input_error(rgb_raster)
    assert "GeoTIFF" in _flood_input_error(tmp_path / "scene.png")


def test_flood_input_validation_accepts_two_band_geotiff(tmp_path):
    sar_raster = _write_raster(tmp_path / "sar.tif", bands=2)
    assert _flood_input_error(sar_raster) is None


def test_flood_validation_blocks_before_cv_execution(tmp_path):
    rgb_raster = _write_raster(tmp_path / "rgb.tif", bands=3)
    pipeline = SimpleNamespace(
        process_query=lambda **kwargs: {
            "capability_validation": {"overall_status": "READY"},
            "routing": {"tasks": [{"task": "FLOODED_AREA_DETECTION"}]},
        },
        registry=SimpleNamespace(execute_tasks=Mock()),
    )
    service = SatQueryInferenceService(pipeline=pipeline)

    result = service.run_analysis("detect flooding", str(rgb_raster))

    assert result["status"] == "blocked"
    assert result["execution"]["execution_started"] is False
    assert "exactly 2 SAR bands" in result["execution"]["validation"]["reason"]
    pipeline.registry.execute_tasks.assert_not_called()


def test_query_endpoint_delegates_to_analysis_contract(monkeypatch):
    response = {"status": "success", "analysis_id": "actual-contract-response"}
    received = {}

    async def fake_run_analysis(payload):
        received["payload"] = payload
        return response

    monkeypatch.setattr(backend_main, "run_analysis", fake_run_analysis)
    client = TestClient(backend_main.app)
    result = client.post(
        "/api/query",
        json={
            "query": "compare buildings",
            "imageId": "before-id",
            "secondImageId": "after-id",
            "sessionId": "ignored-session",
            "context": {"ignored": True},
        },
    )

    assert result.status_code == 200
    assert result.json() == response
    payload = received["payload"]
    assert payload.image == "before-id"
    assert payload.second_image == "after-id"
    assert payload.query == "compare buildings"


def test_query_endpoint_requires_selected_image():
    client = TestClient(backend_main.app)
    result = client.post("/api/query", json={"query": "count buildings"})
    assert result.status_code == 422
    assert "Upload and select" in result.json()["detail"]


def test_change_overlay_endpoint_serves_model_output_from_analysis_record(
    tmp_path, monkeypatch
):
    project_root = tmp_path / "project"
    output_root = project_root / "cv" / "outputs" / "predictions"
    output_root.mkdir(parents=True)
    overlay = output_root / "change_overlay.png"
    Image.new("RGB", (4, 4), color=(255, 0, 0)).save(overlay)
    analysis_id = str(uuid4())

    monkeypatch.setattr(backend_main, "BASE_DIR", project_root / "backend")
    monkeypatch.setattr(
        backend_main,
        "_analysis_records",
        {
            analysis_id: {
                "execution": {
                    "results": [{
                        "result": {"outputs": {"change_overlay": str(overlay)}}
                    }]
                }
            }
        },
    )

    response = TestClient(backend_main.app).get(
        f"/api/analysis/{analysis_id}/change-overlay"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_flood_overlay_endpoint_serves_file_under_prediction_root(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    # cv/models/flood.py defines this default path under cv/outputs/predictions.
    overlay = (
        project_root / "cv" / "outputs" / "predictions" / "flood"
        / "radiance_sen1floods11_v2" / "scene_flood_overlay.png"
    )
    overlay.parent.mkdir(parents=True)
    Image.new("RGBA", (4, 4), color=(0, 180, 255, 150)).save(overlay)
    analysis_id = str(uuid4())
    monkeypatch.setattr(backend_main, "BASE_DIR", project_root / "backend")
    monkeypatch.setattr(backend_main, "_analysis_records", {
        analysis_id: {"execution": {"results": [{
            "result": {"outputs": {"flood_overlay_png": str(overlay)}}
        }]}}
    })

    response = TestClient(backend_main.app).get(f"/api/analysis/{analysis_id}/flood-overlay")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_flood_overlay_endpoint_rejects_png_outside_prediction_root(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    outside = tmp_path / "outside" / "private.png"
    outside.parent.mkdir()
    Image.new("RGBA", (4, 4), color=(255, 0, 0, 255)).save(outside)
    analysis_id = str(uuid4())
    monkeypatch.setattr(backend_main, "BASE_DIR", project_root / "backend")
    monkeypatch.setattr(backend_main, "_analysis_records", {
        analysis_id: {"execution": {"results": [{
            "result": {"outputs": {"flood_overlay_png": str(outside)}}
        }]}}
    })

    response = TestClient(backend_main.app).get(f"/api/analysis/{analysis_id}/flood-overlay")

    assert response.status_code == 404
    assert response.json()["detail"] == "Flood overlay is not available for this analysis."


def test_flood_overlay_endpoint_rejects_invalid_extension_inside_prediction_root(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    output_root = project_root / "cv" / "outputs" / "predictions"
    invalid = output_root / "flood" / "mask.tif"
    invalid.parent.mkdir(parents=True)
    invalid.write_bytes(b"not a png")
    analysis_id = str(uuid4())
    monkeypatch.setattr(backend_main, "BASE_DIR", project_root / "backend")
    monkeypatch.setattr(backend_main, "_analysis_records", {
        analysis_id: {"execution": {"results": [{
            "result": {"outputs": {"flood_overlay_png": str(invalid)}}
        }]}}
    })

    response = TestClient(backend_main.app).get(f"/api/analysis/{analysis_id}/flood-overlay")

    assert response.status_code == 404


def test_analysis_internal_error_is_logged_and_sanitized(monkeypatch, caplog):
    monkeypatch.setattr(
        backend_main,
        "find_uploaded_image",
        lambda _image_id: Path("C:/private/uploaded-image.tif"),
    )

    def raise_internal_error(*_args):
        raise RuntimeError("internal path C:/private/model/checkpoint.pt")

    monkeypatch.setattr(backend_main, "execute_analysis", raise_internal_error)
    client = TestClient(backend_main.app)
    result = client.post(
        "/api/analysis",
        json={"image": "uploaded-id", "query": "count buildings"},
    )

    assert result.status_code == 500
    assert "C:/private" not in result.json()["detail"]
    assert "Analysis failed while processing" in result.json()["detail"]
    assert "internal path C:/private/model/checkpoint.pt" in caplog.text
