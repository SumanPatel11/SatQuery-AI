"""Lightweight CV contract tests; model forwards are mocked, not inferred."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
import rasterio
import torch
from PIL import Image
from rasterio.transform import from_origin

import cv.registry as cv_registry
import cv.models.building as building_module
import cv.models.change_v2 as change_module
import cv.models.flood as flood_module
import cv.models.land_cover as land_cover_module
from nlp.capability_registry import CapabilityRegistry


def _write_rgb(path: Path, size=(64, 48)):
    Image.new("RGB", size, (50, 100, 150)).save(path)
    return path


def _fake_boxes(xyxy, confidences, classes):
    class Values:
        def __init__(self, values):
            self.values = np.asarray(values)

        def cpu(self):
            return self

        def numpy(self):
            return self.values

    return SimpleNamespace(
        xyxy=Values(xyxy),
        conf=Values(confidences),
        cls=Values(classes),
    )


def test_registry_registers_supported_executors_without_loading_models(tmp_path, monkeypatch):
    root = tmp_path
    flood_model_dir = root / "models/cv/radiance_sen1floods11_v2"
    building_checkpoint = root / "runs/detect/runs/detect/spacenet2_building_yolo26n/weights/best.pt"
    change_checkpoint = root / "models/cv/levir_cd_change_v2/best.pt"
    land_checkpoint = root / "models/cv/loveda_land_cover/best.pt"
    flood_model_dir.mkdir(parents=True)
    building_checkpoint.parent.mkdir(parents=True)
    change_checkpoint.parent.mkdir(parents=True)
    land_checkpoint.parent.mkdir(parents=True)

    paths = [
        root / "cv/models/flood.py",
        flood_model_dir / "model.py",
        flood_model_dir / "best.pt",
        root / "cv/models/building.py",
        building_checkpoint,
        root / "cv/models/change_v2.py",
        change_checkpoint,
        root / "cv/models/land_cover.py",
        land_checkpoint,
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"present")

    monkeypatch.setattr(cv_registry, "ROOT", root)
    monkeypatch.setattr(cv_registry, "IMPLEMENTATION", root / "cv/models/flood.py")
    monkeypatch.setattr(cv_registry, "MODEL_DIR", flood_model_dir)
    monkeypatch.setattr(cv_registry, "MODEL_DEFINITION", flood_model_dir / "model.py")
    monkeypatch.setattr(cv_registry, "CHECKPOINT", flood_model_dir / "best.pt")

    registry = cv_registry.create_capability_registry()
    expected = {
        "FLOODED_AREA_DETECTION": flood_module.detect_flood,
        "FLOODED_AREA_PRESENCE": flood_module.detect_flood_presence,
        "BUILDING_DETECTION": building_module.detect_buildings,
        "BUILDING_COUNT": building_module.count_buildings,
        "BUILDING_LOCATE": building_module.locate_buildings,
        "LAND_COVER_DETECTION": land_cover_module.detect_land_cover,
    }
    for name, executor in expected.items():
        assert registry.get(name)["status"] == "AVAILABLE"
        assert registry._capabilities[name]["executor"] is executor

    change_delegate = Mock(return_value={"capability": "BUILDING_CHANGE"})
    monkeypatch.setattr(cv_registry.change_v2_executor, "predict", change_delegate)
    change_executor = registry._capabilities["BUILDING_CHANGE"]["executor"]
    assert registry.get("BUILDING_CHANGE")["status"] == "AVAILABLE"
    change_executor("before.png", second_image_path="after.png", save_outputs=False)
    change_delegate.assert_called_once_with(
        image_path="before.png", second_image_path="after.png", save_outputs=False
    )


def test_registry_missing_checkpoint_stays_unavailable_and_unknown_is_blocked(tmp_path):
    registry = CapabilityRegistry()
    implementation = tmp_path / "implementation.py"
    implementation.write_text("# test implementation", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Missing or empty model artifacts"):
        registry.register(
            "BUILDING_DETECTION",
            executor=lambda: None,
            implementation_path=str(implementation),
            artifact_paths=[str(tmp_path / "missing.pt")],
        )

    assert registry.get("BUILDING_DETECTION")["status"] == "NOT_VERIFIED"
    with pytest.raises(ValueError, match="Unknown CV capability"):
        registry.register(
            "UNSUPPORTED_CAPABILITY",
            executor=lambda: None,
            implementation_path=str(implementation),
            artifact_paths=[str(implementation)],
        )

    result = registry.validate_tasks([{"task": "UNSUPPORTED_CAPABILITY"}])
    assert result["overall_status"] == "BLOCKED"
    assert result["tasks"][0]["capability_status"] == "UNKNOWN"


def test_building_input_validation_rejects_missing_or_unsupported_files(tmp_path):
    detector = building_module.BuildingDetector()
    with pytest.raises(FileNotFoundError):
        detector.predict(tmp_path / "missing.png", save_outputs=False)

    unsupported = tmp_path / "image.bmp"
    unsupported.write_bytes(b"not decoded")
    with pytest.raises(ValueError, match="Unsupported building image format"):
        detector.predict(unsupported, save_outputs=False)


def test_building_detection_response_contract_and_no_save(tmp_path, monkeypatch):
    image_path = _write_rgb(tmp_path / "scene.png")
    output_dir = tmp_path / "must_not_be_created"
    boxes = _fake_boxes(
        [[1, 2, 12, 20], [15, 5, 30, 25]],
        [0.8, 0.6],
        [0, 0],
    )
    prediction = SimpleNamespace(boxes=boxes, plot=Mock(side_effect=AssertionError("plot must not save")))
    model = SimpleNamespace(predict=Mock(return_value=[prediction]))
    detector = building_module.BuildingDetector()
    monkeypatch.setattr(detector, "_load_model", lambda: model)

    result = detector.predict(image_path, output_dir=output_dir, save_outputs=False)

    assert result["capability"] == "BUILDING_DETECTION"
    assert result["building_count"] == len(result["detections"]) == 2
    assert result["outputs"] == {}
    assert not output_dir.exists()
    model.predict.assert_called_once()
    kwargs = model.predict.call_args.kwargs
    assert kwargs["device"] == "cpu"
    assert kwargs["save"] is False
    for detection in result["detections"]:
        assert detection["class_id"] == 0
        assert detection["class_name"] == "building"
        assert isinstance(detection["confidence"], float)
        assert len(detection["bbox_xyxy"]) == 4
        x1, y1, x2, y2 = detection["bbox_xyxy"]
        assert x1 <= x2 and y1 <= y2
        assert len(detection["center"]) == 2


def test_building_public_api_forwards_no_save(monkeypatch):
    predict = Mock(return_value={"outputs": {}})
    monkeypatch.setattr(building_module._detector, "predict", predict)
    building_module.detect_buildings("sample.png", save_outputs=False)
    predict.assert_called_once_with("sample.png", save_outputs=False)


def test_loveda_input_validation_rejects_missing_file(tmp_path):
    predictor = land_cover_module.LandCoverPredictor()
    with pytest.raises(FileNotFoundError):
        predictor.predict(tmp_path / "missing.png", save_outputs=False)


def test_loveda_seven_class_counts_and_no_save(tmp_path, monkeypatch):
    image_path = _write_rgb(tmp_path / "scene.png", size=(70, 50))
    output_dir = tmp_path / "must_not_be_created"
    logits = torch.zeros((1, 7, 256, 256))
    # Unit-test fixture logits assign each output column to one of seven IDs.
    columns = torch.arange(256) % 7
    for class_id in range(7):
        logits[0, class_id, :, columns == class_id] = 5

    class FakeModel:
        def __call__(self, tensor):
            return logits

    predictor = land_cover_module.LandCoverPredictor()
    monkeypatch.setattr(predictor, "_load_model", lambda: FakeModel())
    monkeypatch.setattr(
        Image.Image,
        "save",
        Mock(side_effect=AssertionError("save_outputs=False must not save")),
    )
    result = predictor.predict(image_path, output_dir=output_dir, save_outputs=False)

    assert result["capability"] == "LAND_COVER_DETECTION"
    assert list(result["class_pixel_counts"]) == land_cover_module.CLASS_NAMES
    assert len(result["class_pixel_counts"]) == 7
    assert all(type(value) is int and value >= 0 for value in result["class_pixel_counts"].values())
    assert sum(result["class_pixel_counts"].values()) == 70 * 50
    assert result["outputs"] == {}
    assert not output_dir.exists()
    assert "area" not in result


def test_loveda_public_api_forwards_no_save(monkeypatch):
    predict = Mock(return_value={"outputs": {}})
    monkeypatch.setattr(land_cover_module._predictor, "predict", predict)
    land_cover_module.detect_land_cover("sample.png", save_outputs=False)
    predict.assert_called_once_with("sample.png", save_outputs=False)


def test_change_rejects_missing_and_invalid_pairs(tmp_path):
    executor = change_module.ChangeDetectionV2Executor(checkpoint_path=tmp_path / "unused.pt")
    before = _write_rgb(tmp_path / "before.png")

    with pytest.raises(ValueError, match="requires before and after"):
        executor.predict(before, save_outputs=False)
    with pytest.raises(FileNotFoundError, match="Before/after image path"):
        executor.predict(before, tmp_path / "missing.png", save_outputs=False)


def test_change_rejects_mismatched_dimensions_without_loading_model(tmp_path, monkeypatch):
    before = _write_rgb(tmp_path / "before.png", size=(64, 48))
    after = _write_rgb(tmp_path / "after.png", size=(65, 48))
    executor = change_module.ChangeDetectionV2Executor(checkpoint_path=tmp_path / "unused.pt")
    monkeypatch.setattr(executor, "_load", lambda: setattr(executor, "model", object()))

    with pytest.raises(ValueError, match="dimensions differ"):
        executor.predict(before, after, save_outputs=False)


def test_change_response_pixel_contract_and_no_save(tmp_path, monkeypatch):
    before = _write_rgb(tmp_path / "before.png", size=(64, 48))
    after = _write_rgb(tmp_path / "after.png", size=(64, 48))
    output_dir = tmp_path / "must_not_be_created"
    logits = torch.full((1, 1, 256, 256), -10.0)
    logits.view(-1)[:17] = 10.0

    class FakeModel:
        def __call__(self, before_tensor, after_tensor):
            return logits

    executor = change_module.ChangeDetectionV2Executor(checkpoint_path=tmp_path / "unused.pt")
    executor.model = FakeModel()
    monkeypatch.setattr(
        Image.Image,
        "save",
        Mock(side_effect=AssertionError("save_outputs=False must not save")),
    )
    result = executor.predict(before, after, output_dir=output_dir, save_outputs=False)

    assert result["capability"] == "BUILDING_CHANGE"
    assert (result["image_width"], result["image_height"]) == (64, 48)
    assert result["total_pixels_at_model_resolution"] == 256 * 256
    assert result["changed_pixels_at_model_resolution"] == 17
    assert result["changed_fraction_at_model_resolution"] == 17 / (256 * 256)
    assert result["outputs"] == {}
    assert not output_dir.exists()
    assert "accuracy" not in result
    assert "geographic_area" not in result


def test_change_public_api_forwards_no_save(monkeypatch):
    predict = Mock(return_value={"outputs": {}})
    monkeypatch.setattr(change_module._executor, "predict", predict)
    change_module.detect_building_changes("before.png", "after.png", save_outputs=False)
    predict.assert_called_once_with(
        image_path="before.png", second_image_path="after.png", save_outputs=False
    )


def _write_sar(path, bands=2, width=224, height=224, nan_pixel=False):
    data = np.ones((bands, height, width), dtype=np.float32)
    if nan_pixel and bands == 2:
        data[:, 0, 0] = np.nan
    profile = {
        "driver": "GTiff",
        "width": width,
        "height": height,
        "count": bands,
        "dtype": "float32",
        "transform": from_origin(0, 1, 1, 1),
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data)
    return path


def test_flood_rejects_invalid_band_count_before_loading(tmp_path, monkeypatch):
    image_path = _write_sar(tmp_path / "three_band.tif", bands=3)
    executor = flood_module.RadianceFloodExecutor()
    monkeypatch.setattr(executor, "_load_model", Mock(side_effect=AssertionError("invalid input must stop first")))

    with pytest.raises(ValueError, match="exactly 2 SAR bands"):
        executor.predict(image_path, save_outputs=False)


def test_flood_rejects_too_small_input_before_loading(tmp_path, monkeypatch):
    image_path = _write_sar(tmp_path / "small.tif", width=100, height=100)
    executor = flood_module.RadianceFloodExecutor()
    monkeypatch.setattr(executor, "_load_model", Mock(side_effect=AssertionError("invalid input must stop first")))

    with pytest.raises(ValueError, match="at least 224x224"):
        executor.predict(image_path, save_outputs=False)


def test_flood_response_count_threshold_and_no_save_contract(tmp_path, monkeypatch):
    image_path = _write_sar(tmp_path / "two_band.tif", nan_pixel=True)
    output_dir = tmp_path / "must_not_be_created"
    executor = flood_module.RadianceFloodExecutor()
    monkeypatch.setattr(executor, "_load_model", lambda: object())
    real_rasterio_open = flood_module.rasterio.open

    def reject_write_open(path, *args, **kwargs):
        mode = args[0] if args else kwargs.get("mode", "r")
        if mode != "r":
            raise AssertionError("save_outputs=False must not open an output raster")
        return real_rasterio_open(path, *args, **kwargs)

    monkeypatch.setattr(flood_module.rasterio, "open", reject_write_open)
    monkeypatch.setattr(
        Image.Image,
        "save",
        Mock(side_effect=AssertionError("save_outputs=False must not save")),
    )

    def mocked_tile(_model, sar, valid_mask):
        probabilities = np.full(valid_mask.shape, 0.75, dtype=np.float32)
        probabilities[~valid_mask] = np.nan
        return probabilities, 1

    monkeypatch.setattr(executor, "_infer_full_tile", mocked_tile)
    result = executor.predict(image_path, output_dir=output_dir, save_outputs=False)

    assert result["capability"] == "FLOODED_AREA_DETECTION"
    assert result["model"] == "Radiance SEN1Floods11 v2"
    assert result["input_bands"] == 2
    assert (result["image_width"], result["image_height"]) == (224, 224)
    assert result["valid_pixels"] + result["invalid_pixels"] == 224 * 224
    assert 0 <= result["flood_pixels"] <= result["valid_pixels"]
    assert result["threshold"] == flood_module.THRESHOLD
    assert result["flood_area_pixel_fraction"] == result["flood_pixels"] / result["valid_pixels"]
    assert result["outputs"] == {}
    assert not output_dir.exists()
    assert "probability_map" not in result
    assert "accuracy" not in result


def test_flood_public_api_forwards_no_save(monkeypatch):
    predict = Mock(return_value={"outputs": {}})
    monkeypatch.setattr(flood_module._executor, "predict", predict)
    flood_module.detect_flood("scene.tif", save_outputs=False)
    predict.assert_called_once_with("scene.tif", save_outputs=False)
