
import sys
from pathlib import Path

import numpy as np
import rasterio
import torch


# ============================================================
# PROJECT PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

MODEL_DIR = ROOT / "models" / "cv" / "radiance_sen1floods11_v2"
CHECKPOINT = MODEL_DIR / "best.pt"

DATA_DIR = (
    ROOT / "data" / "raw" / "cv" / "flood"
    / "sen1floods11" / "sen1floods11_v1.1" / "data"
)

IMAGE_ID = "Bolivia_103757"

SAR_PATH = DATA_DIR / "S1GRDHand" / f"{IMAGE_ID}_S1Hand.tif"
LABEL_PATH = DATA_DIR / "LabelHand" / f"{IMAGE_ID}_LabelHand.tif"

OUTPUT_DIR = (
    ROOT / "cv" / "outputs" / "predictions"
    / "flood" / "radiance_sen1floods11_v2"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROBABILITY_PATH = OUTPUT_DIR / f"{IMAGE_ID}_probability.tif"
MASK_PATH = OUTPUT_DIR / f"{IMAGE_ID}_flood_mask.tif"

# ============================================================
# MODEL CONFIGURATION
# ============================================================

PATCH_SIZE = 224
STRIDE = 112

MEAN = np.array([-12.577, -20.265], dtype=np.float32)
STD = np.array([5.176, 5.870], dtype=np.float32)

DEVICE = torch.device("cpu")

# ============================================================
# SLIDING WINDOW
# ============================================================


def get_window_starts(length, patch_size, stride):

    if length < patch_size:
        raise ValueError(
            f"Image dimension {length} is smaller than "
            f"patch size {patch_size}"
        )

    starts = list(range(0, length - patch_size + 1, stride))

    final_start = length - patch_size

    if starts[-1] != final_start:
        starts.append(final_start)

    return starts


# ============================================================
# GEOREFERENCING VALIDATION
# ============================================================


def validate_georeferencing(
    sar_width,
    sar_height,
    sar_transform,
    sar_crs,
    label_width,
    label_height,
    label_transform,
    label_crs
):

    if sar_width != label_width or sar_height != label_height:
        raise ValueError(
            "SAR and label dimensions do not match."
        )

    if sar_crs != label_crs:
        raise ValueError(
            f"SAR and label CRS do not match: "
            f"{sar_crs} != {label_crs}"
        )

    # Allow only negligible floating-point metadata differences.
    if not np.allclose(
        tuple(sar_transform),
        tuple(label_transform),
        rtol=0.0,
        atol=1e-12
    ):
        raise ValueError(
            "SAR and label transforms are spatially different."
        )

    print("Georeferencing validation: PASSED")
    print("Dimensions: MATCH")
    print("CRS: MATCH")
    print("Affine transform: MATCH within numerical tolerance")


# ============================================================
# METRICS
# ============================================================


def calculate_metrics(prediction, ground_truth, threshold):

    tp = int(
        np.logical_and(
            prediction == 1,
            ground_truth == 1
        ).sum()
    )

    fp = int(
        np.logical_and(
            prediction == 1,
            ground_truth == 0
        ).sum()
    )

    fn = int(
        np.logical_and(
            prediction == 0,
            ground_truth == 1
        ).sum()
    )

    tn = int(
        np.logical_and(
            prediction == 0,
            ground_truth == 0
        ).sum()
    )

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    iou = (
        tp / (tp + fp + fn)
        if tp + fp + fn
        else 0.0
    )

    print("\n" + "-" * 50)
    print(f"THRESHOLD: {threshold:.2f}")
    print("-" * 50)

    print(f"TP: {tp}")
    print(f"FP: {fp}")
    print(f"FN: {fn}")
    print(f"TN: {tn}")

    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print(f"IoU:       {iou:.4f}")


# ============================================================
# MAIN PIPELINE
# ============================================================


def main():

    print("=" * 60)
    print("RADIANCE SEN1FLOODS11 — FULL TILE EVALUATION")
    print("=" * 60)

    # --------------------------------------------------------
    # CHECK REQUIRED FILES
    # --------------------------------------------------------

    required_files = [
        CHECKPOINT,
        MODEL_DIR / "model.py",
        SAR_PATH,
        LABEL_PATH
    ]

    for path in required_files:

        if not path.is_file():
            raise FileNotFoundError(
                f"Required file not found: {path}"
            )

    # --------------------------------------------------------
    # LOAD MODEL
    # --------------------------------------------------------

    sys.path.insert(0, str(MODEL_DIR))

    from model import (
        radiance_mae_vit_base,
        RadianceSegModel
    )

    print("\nLoading model architecture...")

    model = RadianceSegModel(
        radiance_mae_vit_base()
    )

    print("Loading checkpoint...")

    checkpoint = torch.load(
        CHECKPOINT,
        map_location=DEVICE,
        weights_only=True
    )

    model.load_state_dict(
        checkpoint["model"],
        strict=True
    )

    model.to(DEVICE)
    model.eval()

    print("Strict checkpoint loading: SUCCESS")
    print(f"Device: {DEVICE}")

    # --------------------------------------------------------
    # READ SAR IMAGE
    # --------------------------------------------------------

    print("\nReading SAR image...")

    with rasterio.open(SAR_PATH) as src:

        sar = src.read().astype(np.float32)

        profile = src.profile.copy()

        transform = src.transform
        crs = src.crs

        height = src.height
        width = src.width

    if sar.shape[0] != 2:
        raise ValueError(
            f"Expected 2 SAR bands, received {sar.shape[0]}"
        )

    if height < PATCH_SIZE or width < PATCH_SIZE:
        raise ValueError(
            f"Image dimensions are too small: {height}x{width}"
        )

    # A pixel is valid only when both SAR bands are finite.
    valid_mask = np.isfinite(sar).all(axis=0)

    # --------------------------------------------------------
    # PREPROCESSING
    # --------------------------------------------------------

    processed = np.nan_to_num(
        sar,
        nan=0.0,
        posinf=0.0,
        neginf=0.0
    )

    processed = np.clip(
        processed,
        -60.0,
        20.0
    )

    processed = (
        processed - MEAN[:, None, None]
    ) / STD[:, None, None]

    print(f"Image dimensions: {height} x {width}")
    print(f"Valid SAR pixels: {int(valid_mask.sum())}")

    # --------------------------------------------------------
    # SLIDING WINDOW SETUP
    # --------------------------------------------------------

    y_starts = get_window_starts(
        height,
        PATCH_SIZE,
        STRIDE
    )

    x_starts = get_window_starts(
        width,
        PATCH_SIZE,
        STRIDE
    )

    total_windows = len(y_starts) * len(x_starts)

    print(f"Window size: {PATCH_SIZE} x {PATCH_SIZE}")
    print(f"Stride: {STRIDE}")
    print(f"Total windows: {total_windows}")

    probability_sum = np.zeros(
        (height, width),
        dtype=np.float32
    )

    prediction_count = np.zeros(
        (height, width),
        dtype=np.uint16
    )

    # --------------------------------------------------------
    # FULL TILE INFERENCE
    # --------------------------------------------------------

    print("\nRunning sliding-window inference...")

    window_number = 0

    with torch.inference_mode():

        for y in y_starts:

            for x in x_starts:

                window_number += 1

                patch = processed[
                    :,
                    y:y + PATCH_SIZE,
                    x:x + PATCH_SIZE
                ]

                input_tensor = torch.from_numpy(
                    patch.copy()
                ).unsqueeze(0).to(DEVICE)

                logits = model(input_tensor)

                probabilities = torch.sigmoid(logits)

                probability_patch = (
                    probabilities
                    .squeeze()
                    .cpu()
                    .numpy()
                    .astype(np.float32)
                )

                if probability_patch.shape != (
                    PATCH_SIZE,
                    PATCH_SIZE
                ):

                    raise RuntimeError(
                        f"Unexpected output shape: "
                        f"{probability_patch.shape}"
                    )

                probability_sum[
                    y:y + PATCH_SIZE,
                    x:x + PATCH_SIZE
                ] += probability_patch

                prediction_count[
                    y:y + PATCH_SIZE,
                    x:x + PATCH_SIZE
                ] += 1

                print(
                    f"Processed window "
                    f"{window_number}/{total_windows}",
                    end="\r"
                )

    print("\n\nReconstructing full probability map...")

    if np.any(prediction_count == 0):

        raise RuntimeError(
            "Some image pixels were not covered by inference windows."
        )

    probability_map = (
        probability_sum /
        prediction_count.astype(np.float32)
    )

    # Ignore predictions over invalid SAR pixels.
    probability_map[~valid_mask] = np.nan

    print("Probability map reconstructed.")

    print(
        "Finite probability pixels:",
        int(np.isfinite(probability_map).sum())
    )

    # --------------------------------------------------------
    # READ AND VALIDATE GROUND TRUTH
    # --------------------------------------------------------

    print("\nReading ground-truth labels...")

    with rasterio.open(LABEL_PATH) as src:

        labels = src.read(1)

        label_width = src.width
        label_height = src.height

        label_transform = src.transform
        label_crs = src.crs

    validate_georeferencing(
        width,
        height,
        transform,
        crs,
        label_width,
        label_height,
        label_transform,
        label_crs
    )

    # SEN1Floods11:
    # -1 = unknown
    #  0 = non-flood
    #  1 = flood

    evaluation_mask = (
        valid_mask &
        np.isin(labels, [0, 1])
    )

    if not evaluation_mask.any():

        raise RuntimeError(
            "No valid pixels available for evaluation."
        )

    ground_truth = labels[
        evaluation_mask
    ].astype(np.uint8)

    evaluated_probabilities = probability_map[
        evaluation_mask
    ]

    print(
        f"Valid evaluation pixels: {len(ground_truth)}"
    )

    print(
        "Ground-truth flood pixels:",
        int((ground_truth == 1).sum())
    )

    print(
        "Ground-truth non-flood pixels:",
        int((ground_truth == 0).sum())
    )

    # --------------------------------------------------------
    # EVALUATE TWO THRESHOLDS
    # --------------------------------------------------------

    for threshold in (0.25, 0.50):

        predictions = (
            evaluated_probabilities >= threshold
        ).astype(np.uint8)

        calculate_metrics(
            predictions,
            ground_truth,
            threshold
        )

    # --------------------------------------------------------
    # SAVE PROBABILITY GEOTIFF
    # --------------------------------------------------------

    print("\nSaving georeferenced probability map...")

    probability_profile = profile.copy()

    probability_profile.update(
        count=1,
        dtype="float32",
        nodata=np.nan,
        compress="deflate"
    )

    with rasterio.open(
        PROBABILITY_PATH,
        "w",
        **probability_profile
    ) as dst:

        dst.write(
            probability_map.astype(np.float32),
            1
        )

    print("Probability map saved.")

    # --------------------------------------------------------
    # SAVE BINARY FLOOD MASK
    # --------------------------------------------------------

    print(
        "\nSaving georeferenced binary flood mask..."
    )

    # 255 = invalid / nodata
    # 0   = non-flood
    # 1   = flood

    binary_mask = np.full(
        (height, width),
        255,
        dtype=np.uint8
    )

    binary_mask[valid_mask] = (
        probability_map[valid_mask] >= 0.25
    ).astype(np.uint8)

    mask_profile = profile.copy()

    mask_profile.update(
        count=1,
        dtype="uint8",
        nodata=255,
        compress="deflate"
    )

    with rasterio.open(
        MASK_PATH,
        "w",
        **mask_profile
    ) as dst:

        dst.write(
            binary_mask,
            1
        )

    # --------------------------------------------------------
    # COMPLETION
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("FULL TILE EVALUATION COMPLETE")
    print("=" * 60)

    print(f"Probability GeoTIFF: {PROBABILITY_PATH}")
    print(f"Binary mask GeoTIFF: {MASK_PATH}")

    print("Saved mask threshold: 0.25")
    print("No training or fine-tuning was performed.")


if __name__ == "__main__":
    main()
