from pathlib import Path
import threading

import numpy as np
import rasterio
from PIL import Image
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[2]

CHECKPOINT = (
    ROOT / "runs" / "detect" / "runs" / "detect"
    / "spacenet2_building_yolo26n" / "weights" / "best.pt"
)

OUTPUT_DIR = ROOT / "cv" / "outputs" / "predictions" / "building"

LIMITS_LOW = np.array([127.0, 225.0, 224.0], dtype=np.float32)
LIMITS_HIGH = np.array([486.0, 504.0, 380.0], dtype=np.float32)

DEVICE = "cpu"
IMAGE_SIZE = 512
CONFIDENCE = 0.25


class BuildingDetector:

    def __init__(self):
        self._model = None
        self._lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def _load_model(self):
        if self._model is not None:
            return self._model

        with self._lock:
            if self._model is not None:
                return self._model

            if not CHECKPOINT.is_file():
                raise FileNotFoundError(CHECKPOINT)

            model = YOLO(str(CHECKPOINT))
            self._model = model

        return self._model

    @staticmethod
    def _read_image(image_path):
        image_path = Path(image_path)
        suffix = image_path.suffix.lower()

        if suffix in {".tif", ".tiff"}:
            with rasterio.open(image_path) as src:
                if src.count != 3:
                    raise ValueError(
                        "Building model requires exactly 3 RGB bands."
                    )

                data = src.read([1, 2, 3]).astype(np.float32)

            rgb = np.empty(data.shape, dtype=np.uint8)

            for band in range(3):
                scaled = (
                    (data[band] - LIMITS_LOW[band])
                    * 255.0
                    / (LIMITS_HIGH[band] - LIMITS_LOW[band])
                )
                rgb[band] = np.clip(scaled, 0, 255).astype(np.uint8)

            return np.moveaxis(rgb, 0, -1)

        if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
            with Image.open(image_path) as image:
                return np.asarray(image.convert("RGB"))

        raise ValueError("Unsupported building image format.")

    def predict(
        self,
        image_path,
        output_dir=None,
        save_outputs=True,
    ):
        image_path = Path(image_path)

        if not image_path.is_file():
            raise FileNotFoundError(image_path)

        rgb = self._read_image(image_path)

        if rgb.ndim != 3 or rgb.shape[2] != 3:
            raise ValueError("Expected a 3-channel RGB image.")

        model = self._load_model()

        with self._inference_lock:
            predictions = model.predict(
                source=rgb,
                imgsz=IMAGE_SIZE,
                conf=CONFIDENCE,
                device=DEVICE,
                verbose=False,
                save=False,
            )

        result = predictions[0]
        boxes = result.boxes

        detections = []

        if boxes is not None:
            xyxy = boxes.xyxy.cpu().numpy()
            confidences = boxes.conf.cpu().numpy()
            classes = boxes.cls.cpu().numpy().astype(int)

            for coordinates, confidence, class_id in zip(
                xyxy, confidences, classes
            ):
                x1, y1, x2, y2 = coordinates.tolist()

                detections.append({
                    "class_id": int(class_id),
                    "class_name": "building",
                    "confidence": float(confidence),
                    "bbox_xyxy": [
                        float(x1), float(y1),
                        float(x2), float(y2),
                    ],
                    "center": [
                        float((x1 + x2) / 2),
                        float((y1 + y2) / 2),
                    ],
                })

        outputs = {}

        if save_outputs:
            destination = Path(output_dir) if output_dir else OUTPUT_DIR
            destination.mkdir(parents=True, exist_ok=True)

            annotated_path = destination / f"{image_path.stem}_buildings.jpg"

            annotated = result.plot()
            Image.fromarray(annotated[:, :, ::-1]).save(
                annotated_path,
                format="JPEG",
                quality=95,
            )

            outputs["annotated_image"] = str(annotated_path)

        return {
            "capability": "BUILDING_DETECTION",
            "model": "YOLO26n SpaceNet2",
            "checkpoint": str(CHECKPOINT),
            "input": str(image_path),
            "image_width": int(rgb.shape[1]),
            "image_height": int(rgb.shape[0]),
            "building_count": len(detections),
            "detections": detections,
            "device": DEVICE,
            "training_performed": False,
            "outputs": outputs,
        }


_detector = BuildingDetector()


def detect_buildings(image_path, **kwargs):
    return _detector.predict(image_path, **kwargs)


def count_buildings(image_path, **kwargs):
    result = detect_buildings(image_path, **kwargs)

    return {
        **result,
        "capability": "BUILDING_COUNT",
    }


def locate_buildings(image_path, **kwargs):
    result = detect_buildings(image_path, **kwargs)

    return {
        **result,
        "capability": "BUILDING_LOCATE",
    }
