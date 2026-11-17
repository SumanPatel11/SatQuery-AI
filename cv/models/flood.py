from pathlib import Path
import sys
import threading

import numpy as np
import rasterio
import torch
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]

MODEL_DIR = ROOT / "models" / "cv" / "radiance_sen1floods11_v2"
CHECKPOINT = MODEL_DIR / "best.pt"

OUTPUT_DIR = (
    ROOT / "cv" / "outputs" / "predictions"
    / "flood" / "radiance_sen1floods11_v2"
)

PATCH_SIZE = 224
STRIDE = 112
THRESHOLD = 0.50

MEAN = np.array([-12.577, -20.265], dtype=np.float32)
STD = np.array([5.176, 5.870], dtype=np.float32)

DEVICE = torch.device("cpu")


def get_window_starts(length):
    if length < PATCH_SIZE:
        raise ValueError(
            f"Image dimension too small: {length}. "
            f"Minimum supported dimension is {PATCH_SIZE}."
        )

    starts = list(range(0, length - PATCH_SIZE + 1, STRIDE))
    final_start = length - PATCH_SIZE

    if starts[-1] != final_start:
        starts.append(final_start)

    return starts


class RadianceFloodExecutor:
    """Inference-only executor for Radiance SEN1Floods11 v2."""

    def __init__(self):
        self._model = None
        self._lock = threading.Lock()
        self._inference_lock = threading.Lock()
        self._checkpoint_epoch = None

    def _load_model(self):
        if self._model is not None:
            return self._model

        with self._lock:
            if self._model is not None:
                return self._model

            if not CHECKPOINT.is_file():
                raise FileNotFoundError(CHECKPOINT)

            model_file = MODEL_DIR / "model.py"

            if not model_file.is_file() or model_file.stat().st_size == 0:
                raise FileNotFoundError(model_file)

            model_path = str(MODEL_DIR)

            if model_path not in sys.path:
                sys.path.insert(0, model_path)

            from model import radiance_mae_vit_base, RadianceSegModel

            model = RadianceSegModel(radiance_mae_vit_base())

            checkpoint = torch.load(
                CHECKPOINT,
                map_location=DEVICE,
                weights_only=True,
            )

            model.load_state_dict(checkpoint["model"], strict=True)
            model.to(DEVICE)
            model.eval()

            self._checkpoint_epoch = checkpoint.get("epoch")
            self._model = model

        return self._model

    def _infer_full_tile(self, model, sar, valid_mask):
        _, height, width = sar.shape

        processed = np.nan_to_num(
            sar,
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )

        processed = np.clip(processed, -60.0, 20.0)

        processed = (
            processed - MEAN[:, None, None]
        ) / STD[:, None, None]

        y_starts = get_window_starts(height)
        x_starts = get_window_starts(width)

        probability_sum = np.zeros(
            (height, width), dtype=np.float32
        )

        prediction_count = np.zeros(
            (height, width), dtype=np.uint16
        )

        total_windows = len(y_starts) * len(x_starts)

        with torch.inference_mode():
            for y in y_starts:
                for x in x_starts:
                    patch = processed[
                        :,
                        y:y + PATCH_SIZE,
                        x:x + PATCH_SIZE,
                    ]

                    tensor = torch.from_numpy(
                        patch.copy()
                    ).unsqueeze(0).to(DEVICE)

                    logits = model(tensor)
                    probabilities = torch.sigmoid(logits)

                    probability_patch = (
                        probabilities.squeeze()
                        .cpu()
                        .numpy()
                        .astype(np.float32)
                    )

                    if probability_patch.shape != (
                        PATCH_SIZE, PATCH_SIZE
                    ):
                        raise RuntimeError(
                            "Unexpected model output shape: "
                            f"{probability_patch.shape}"
                        )

                    probability_sum[
                        y:y + PATCH_SIZE,
                        x:x + PATCH_SIZE,
                    ] += probability_patch

                    prediction_count[
                        y:y + PATCH_SIZE,
                        x:x + PATCH_SIZE,
                    ] += 1

        if np.any(prediction_count == 0):
            raise RuntimeError("Uncovered image pixels detected.")

        probability_map = (
            probability_sum /
            prediction_count.astype(np.float32)
        )

        probability_map[~valid_mask] = np.nan

        return probability_map, total_windows

    def predict(
        self,
        image_path,
        output_dir=None,
        save_outputs=True,
    ):
        image_path = Path(image_path)

        if not image_path.is_file():
            raise FileNotFoundError(image_path)

        with rasterio.open(image_path) as src:
            if src.count != 2:
                raise ValueError(
                    "Radiance requires exactly 2 SAR bands. "
                    f"Received {src.count} bands."
                )

            if src.width < PATCH_SIZE or src.height < PATCH_SIZE:
                raise ValueError(
                    f"Image must be at least {PATCH_SIZE}x{PATCH_SIZE}."
                )

            sar = src.read().astype(np.float32)
            profile = src.profile.copy()

            valid_mask = np.isfinite(sar).all(axis=0)

        valid_pixels = int(valid_mask.sum())

        if valid_pixels == 0:
            raise ValueError(
                "SAR image contains no pixels with both bands finite."
            )

        model = self._load_model()

        # Protect shared model inference if multiple requests arrive.
        with self._inference_lock:
            probability_map, total_windows = self._infer_full_tile(
                model,
                sar,
                valid_mask,
            )

        flood_mask = (
            (probability_map >= THRESHOLD) & valid_mask
        ).astype(np.uint8)

        flood_pixels = int(flood_mask.sum())

        results = {
            "capability": "FLOODED_AREA_DETECTION",
            "model": "Radiance SEN1Floods11 v2",
            "checkpoint": str(CHECKPOINT),
            "checkpoint_epoch": self._checkpoint_epoch,
            "threshold": THRESHOLD,
            "input": str(image_path),
            "input_bands": 2,
            "image_width": int(profile["width"]),
            "image_height": int(profile["height"]),
            "valid_pixels": valid_pixels,
            "invalid_pixels": int(valid_mask.size - valid_pixels),
            "flood_pixels": flood_pixels,
            "flood_area_pixel_fraction": flood_pixels / valid_pixels,
            "windows_processed": total_windows,
            "device": str(DEVICE),
            "training_performed": False,
            "outputs": {},
        }

        if save_outputs:
            destination = (
                Path(output_dir) if output_dir else OUTPUT_DIR
            )

            destination.mkdir(parents=True, exist_ok=True)

            stem = image_path.stem

            probability_path = (
                destination / f"{stem}_probability.tif"
            )

            mask_path = destination / f"{stem}_flood_mask.tif"
            overlay_path = destination / f"{stem}_flood_overlay.png"

            probability_profile = profile.copy()
            probability_profile.update(
                count=1,
                dtype="float32",
                nodata=np.nan,
                compress="deflate",
            )

            mask_profile = profile.copy()
            mask_profile.update(
                count=1,
                dtype="uint8",
                nodata=255,
                compress="deflate",
            )

            with rasterio.open(
                probability_path,
                "w",
                **probability_profile,
            ) as dst:
                dst.write(probability_map.astype(np.float32), 1)

            output_mask = flood_mask.copy()
            output_mask[~valid_mask] = 255

            with rasterio.open(
                mask_path,
                "w",
                **mask_profile,
            ) as dst:
                dst.write(output_mask, 1)

            rgba = np.zeros(
                (flood_mask.shape[0], flood_mask.shape[1], 4),
                dtype=np.uint8,
            )
            rgba[flood_mask == 1] = (0, 180, 255, 150)

            Image.fromarray(rgba).save(overlay_path)

            results["outputs"] = {
                "probability_map": str(probability_path),
                "flood_mask": str(mask_path),
                "flood_overlay_png": str(overlay_path),
            }

        return results


_executor = RadianceFloodExecutor()


def detect_flood(image_path, **kwargs):
    return _executor.predict(image_path, **kwargs)


def detect_flood_presence(image_path, **kwargs):
    result = detect_flood(image_path, **kwargs)

    return {
        **result,
        "capability": "FLOODED_AREA_PRESENCE",
        "flood_present": result["flood_pixels"] > 0,
    }
