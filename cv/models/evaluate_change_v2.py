from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from cv.models.change_v2 import LevirCDDataset, SiameseAttentionChangeNet


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHECKPOINT = ROOT / "models/cv/levir_cd_change_v2/best.pt"
DEFAULT_DATASET = ROOT / "data/raw/cv/change/levir_cd"


@torch.no_grad()
def evaluate_test(model, loader, threshold, device):
    model.eval()
    tp = fp = fn = tn = 0
    loss_total = 0.0
    batches = 0

    for before, after, target in loader:
        before = before.to(device)
        after = after.to(device)
        target = target.to(device)

        logits = model(before, after)
        probabilities = torch.sigmoid(logits)
        predictions = probabilities >= threshold
        actual = target >= 0.5

        tp += int((predictions & actual).sum().item())
        fp += int((predictions & ~actual).sum().item())
        fn += int((~predictions & actual).sum().item())
        tn += int((~predictions & ~actual).sum().item())
        batches += 1

    eps = 1e-8
    precision = tp / (tp + fp + eps)
    recall = tp / (tp + fn + eps)
    f1 = 2 * precision * recall / (precision + recall + eps)
    iou = tp / (tp + fp + fn + eps)
    pixel_accuracy = (tp + tn) / (tp + tn + fp + fn + eps)

    return {
        "split": "test",
        "threshold_from_validation_checkpoint": float(threshold),
        "test_pairs": len(loader.dataset),
        "change_iou": iou,
        "f1": f1,
        "precision": precision,
        "recall": recall,
        "pixel_accuracy": pixel_accuracy,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "batches": batches,
        "note": (
            "Threshold was loaded from the validation-selected checkpoint; "
            "it was not tuned on the test split."
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate the saved V2 LEVIR-CD checkpoint on untouched test data."
    )
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--dataset-root", default=str(DEFAULT_DATASET))
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--threads", type=int, default=6)
    args = parser.parse_args()

    checkpoint_path = Path(args.checkpoint)
    dataset_root = Path(args.dataset_root)

    if not checkpoint_path.is_file() or checkpoint_path.stat().st_size == 0:
        raise FileNotFoundError(f"Checkpoint missing or empty: {checkpoint_path}")

    test_set = LevirCDDataset(
        dataset_root, "test", image_size=256, augment=False
    )

    torch.set_num_threads(args.threads)
    device = torch.device("cpu")

    checkpoint = torch.load(
        checkpoint_path, map_location=device, weights_only=False
    )
    model = SiameseAttentionChangeNet().to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    image_size = int(checkpoint.get("image_size", 256))
    if image_size != 256:
        test_set = LevirCDDataset(
            dataset_root, "test", image_size=image_size, augment=False
        )

    threshold = float(checkpoint.get("threshold", 0.5))
    loader = DataLoader(
        test_set,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
    )

    print(f"Checkpoint: {checkpoint_path}")
    print(f"Checkpoint epoch: {checkpoint.get('epoch', 'unknown')}")
    print(f"Validation-selected threshold: {threshold:.2f}")
    print(f"Test pairs: {len(test_set)}")
    print("Running test evaluation without threshold tuning...", flush=True)

    metrics = evaluate_test(model, loader, threshold, device)
    print("\n========== UNTOUCHED TEST RESULTS ==========")
    for key in (
        "change_iou", "f1", "precision", "recall", "pixel_accuracy"
    ):
        print(f"{key}: {metrics[key]:.4f} ({metrics[key] * 100:.2f}%)")
    print(
        f"TP: {metrics['tp']} | FP: {metrics['fp']} | "
        f"FN: {metrics['fn']} | TN: {metrics['tn']}"
    )

    output_path = checkpoint_path.parent / "test_metrics.json"
    output_path.write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    print(f"\nMetrics saved to: {output_path}")
    print("Checkpoint was loaded read-only and was not modified.")


if __name__ == "__main__":
    main()
