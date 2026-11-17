import sys
import csv
import json
from pathlib import Path

import numpy as np
import rasterio
import torch

ROOT = Path(__file__).resolve().parents[2]

MODEL_DIR = ROOT / "models" / "cv" / "radiance_sen1floods11_v2"
CHECKPOINT = MODEL_DIR / "best.pt"

DATA_ROOT = (
    ROOT / "data" / "raw" / "cv" / "flood"
    / "sen1floods11" / "sen1floods11_v1.1"
)

DATA_DIR = DATA_ROOT / "data"
SPLIT_FILE = DATA_ROOT / "splits" / "flood_valid_data.txt"

OUTPUT_DIR = (
    ROOT / "cv" / "outputs" / "evaluation"
    / "radiance_sen1floods11_v2" / "validation"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PATCH_SIZE = 224
STRIDE = 112

MEAN = np.array([-12.577, -20.265], dtype=np.float32)
STD = np.array([5.176, 5.870], dtype=np.float32)

THRESHOLDS = (0.25, 0.50)
DEVICE = torch.device("cpu")


def get_window_starts(length):
    if length < PATCH_SIZE:
        raise ValueError(f"Image dimension too small: {length}")

    starts = list(range(0, length - PATCH_SIZE + 1, STRIDE))
    final_start = length - PATCH_SIZE

    if starts[-1] != final_start:
        starts.append(final_start)

    return starts


def calculate_metrics(tp, fp, fn, tn):
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )

    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0

    return {
        "TP": int(tp),
        "FP": int(fp),
        "FN": int(fn),
        "TN": int(tn),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "iou": iou,
    }


def validate_georeferencing(sar_src, label_src):
    if (
        sar_src.width != label_src.width
        or sar_src.height != label_src.height
    ):
        raise ValueError("SAR and label dimensions differ.")

    if sar_src.crs != label_src.crs:
        raise ValueError("SAR and label CRS differ.")

    if not np.allclose(
        tuple(sar_src.transform),
        tuple(label_src.transform),
        rtol=0.0,
        atol=1e-12,
    ):
        raise ValueError("SAR and label transforms differ.")


def load_model():
    if not CHECKPOINT.is_file():
        raise FileNotFoundError(CHECKPOINT)

    if not (MODEL_DIR / "model.py").is_file():
        raise FileNotFoundError(MODEL_DIR / "model.py")

    sys.path.insert(0, str(MODEL_DIR))

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

    print("Strict checkpoint loading: SUCCESS")
    print("Checkpoint epoch:", checkpoint.get("epoch"))
    print("Device:", DEVICE)

    return model


def infer_full_tile(model, sar, valid_mask):
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

    probability_sum = np.zeros((height, width), dtype=np.float32)
    prediction_count = np.zeros((height, width), dtype=np.uint16)

    total_windows = len(y_starts) * len(x_starts)
    completed = 0

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
                    probabilities.squeeze().cpu().numpy().astype(np.float32)
                )

                if probability_patch.shape != (PATCH_SIZE, PATCH_SIZE):
                    raise RuntimeError(
                        f"Unexpected output shape: {probability_patch.shape}"
                    )

                probability_sum[
                    y:y + PATCH_SIZE,
                    x:x + PATCH_SIZE,
                ] += probability_patch

                prediction_count[
                    y:y + PATCH_SIZE,
                    x:x + PATCH_SIZE,
                ] += 1

                completed += 1

                print(
                    f"    Windows: {completed}/{total_windows}",
                    end="\r",
                    flush=True,
                )

    print()

    if np.any(prediction_count == 0):
        raise RuntimeError("Uncovered pixels detected.")

    probability_map = (
        probability_sum / prediction_count.astype(np.float32)
    )

    probability_map[~valid_mask] = np.nan

    return probability_map, total_windows


def evaluate_scene(model, scene_id):
    sar_path = DATA_DIR / "S1GRDHand" / f"{scene_id}_S1Hand.tif"
    label_path = DATA_DIR / "LabelHand" / f"{scene_id}_LabelHand.tif"

    if not sar_path.is_file():
        raise FileNotFoundError(sar_path)

    if not label_path.is_file():
        raise FileNotFoundError(label_path)

    with rasterio.open(sar_path) as sar_src:
        sar = sar_src.read().astype(np.float32)
        profile = sar_src.profile.copy()

        if sar.shape[0] != 2:
            raise ValueError(f"{scene_id}: expected two SAR bands.")

        valid_mask = np.isfinite(sar).all(axis=0)

        with rasterio.open(label_path) as label_src:
            validate_georeferencing(sar_src, label_src)
            labels = label_src.read(1)

    evaluation_mask = valid_mask & np.isin(labels, [0, 1])

    if not evaluation_mask.any():
        raise ValueError(f"{scene_id}: no valid evaluation pixels.")

    probability_map, total_windows = infer_full_tile(
        model,
        sar,
        valid_mask,
    )

    ground_truth = labels[evaluation_mask].astype(np.uint8)
    probabilities = probability_map[evaluation_mask]

    scene_results = {
        "scene_id": scene_id,
        "width": int(sar.shape[2]),
        "height": int(sar.shape[1]),
        "windows": total_windows,
        "valid_sar_pixels": int(valid_mask.sum()),
        "evaluated_pixels": int(evaluation_mask.sum()),
        "ground_truth_flood_pixels": int((ground_truth == 1).sum()),
        "ground_truth_non_flood_pixels": int((ground_truth == 0).sum()),
    }

    for threshold in THRESHOLDS:
        prediction = (probabilities >= threshold).astype(np.uint8)

        tp = int(((prediction == 1) & (ground_truth == 1)).sum())
        fp = int(((prediction == 1) & (ground_truth == 0)).sum())
        fn = int(((prediction == 0) & (ground_truth == 1)).sum())
        tn = int(((prediction == 0) & (ground_truth == 0)).sum())

        metrics = calculate_metrics(tp, fp, fn, tn)

        for key, value in metrics.items():
            scene_results[f"threshold_{threshold:.2f}_{key}"] = value

    return scene_results


def main():
    print("=" * 65)
    print("RADIANCE SEN1FLOODS11 — VALIDATION BATCH EVALUATION")
    print("=" * 65)

    required = [CHECKPOINT, MODEL_DIR / "model.py", SPLIT_FILE]

    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)

    scene_ids = [
        line.strip()
        for line in SPLIT_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    if len(scene_ids) != 89:
        raise ValueError(
            f"Expected 89 validation scenes, found {len(scene_ids)}."
        )

    if len(scene_ids) != len(set(scene_ids)):
        raise ValueError("Duplicate validation scene IDs detected.")

    print("Validation scenes:", len(scene_ids))
    print("Thresholds:", THRESHOLDS)
    print("Inference: full tile, sliding window")
    print("Training/fine-tuning: NOT performed")

    model = load_model()

    results = []
    failures = []

    for index, scene_id in enumerate(scene_ids, start=1):
        print(f"\n[{index}/{len(scene_ids)}] {scene_id}")

        try:
            result = evaluate_scene(model, scene_id)
            results.append(result)

            print(
                f"  Pixels: {result['evaluated_pixels']:,} | "
                f"IoU@0.50: {result['threshold_0.50_iou']:.4f}"
            )

        except Exception as exc:
            failures.append({
                "scene_id": scene_id,
                "error": str(exc),
            })
            print("  FAILED:", str(exc))

    csv_path = OUTPUT_DIR / "validation_per_scene.csv"
    json_path = OUTPUT_DIR / "validation_aggregate.json"
    failure_path = OUTPUT_DIR / "validation_failures.json"

    if results:
        fieldnames = list(results[0].keys())

        with csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

    aggregate = {
        "split": "validation",
        "expected_scenes": 89,
        "completed_scenes": len(results),
        "failed_scenes": len(failures),
        "thresholds": {},
        "aggregation": "global pixel-level confusion matrix",
        "checkpoint": str(CHECKPOINT),
        "inference": "224x224 sliding windows, stride 112, overlap probability averaging",
    }

    for threshold in THRESHOLDS:
        prefix = f"threshold_{threshold:.2f}_"

        totals = {
            key: sum(
                int(row[prefix + key])
                for row in results
            )
            for key in ("TP", "FP", "FN", "TN")
        }

        aggregate["thresholds"][str(threshold)] = calculate_metrics(
            totals["TP"],
            totals["FP"],
            totals["FN"],
            totals["TN"],
        )

    json_path.write_text(
        json.dumps(aggregate, indent=2),
        encoding="utf-8",
    )

    failure_path.write_text(
        json.dumps(failures, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 65)
    print("VALIDATION BATCH SUMMARY")
    print("=" * 65)

    print("Completed:", len(results), "/", len(scene_ids))
    print("Failed:", len(failures))

    for threshold, metrics in aggregate["thresholds"].items():
        print(f"\nTHRESHOLD {threshold}")
        print("TP:", metrics["TP"])
        print("FP:", metrics["FP"])
        print("FN:", metrics["FN"])
        print("TN:", metrics["TN"])
        print(f"Precision: {metrics['precision']:.4f}")
        print(f"Recall:    {metrics['recall']:.4f}")
        print(f"F1:        {metrics['f1']:.4f}")
        print(f"IoU:       {metrics['iou']:.4f}")

    print("\nPer-scene CSV:", csv_path)
    print("Aggregate JSON:", json_path)
    print("Failures JSON:", failure_path)

    if failures:
        print("\nWARNING: Some scenes failed. Do not treat this as a complete evaluation.")
    else:
        print("\nALL VALIDATION SCENES COMPLETED.")

    print("No training or fine-tuning was performed.")


if __name__ == "__main__":
    main()
