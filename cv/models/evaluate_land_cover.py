
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from cv.models.land_cover import (
    ROOT,
    DEVICE,
    CHECKPOINT,
    LoveDADataset,
    LoveDASegmenter,
    load_config,
    CLASS_NAMES,
    IGNORE_INDEX,
)


def evaluate():
    config = load_config()

    torch.set_num_threads(config.get("cpu_threads", 6))

    if not CHECKPOINT.is_file():
        raise FileNotFoundError(CHECKPOINT)

    print("Loading existing checkpoint...")

    checkpoint = torch.load(
        CHECKPOINT,
        map_location=DEVICE,
        weights_only=False
    )

    dataset_root = ROOT / config["dataset_root"]

    val_data = LoveDADataset(
        dataset_root,
        "Val",
        checkpoint["image_size"],
        limit=None
    )

    val_loader = DataLoader(
        val_data,
        batch_size=1,
        shuffle=False,
        num_workers=0
    )

    model = LoveDASegmenter(checkpoint["num_classes"]).to(DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    num_classes = checkpoint["num_classes"]

    confusion = torch.zeros(
        (num_classes, num_classes),
        dtype=torch.int64
    )

    print("Checkpoint loaded successfully.")
    print("Validation images:", len(val_data))
    print("Starting evaluation...")

    with torch.no_grad():
        for index, (images, masks) in enumerate(val_loader):

            images = images.to(DEVICE)
            masks = masks.to(DEVICE)

            predictions = model(images).argmax(dim=1)

            valid = masks != IGNORE_INDEX

            actual = masks[valid].cpu()
            predicted = predictions[valid].cpu()

            encoded = actual * num_classes + predicted

            confusion += torch.bincount(
                encoded,
                minlength=num_classes * num_classes
            ).reshape(num_classes, num_classes)

            if (index + 1) % 100 == 0:
                print(
                    f"Evaluated {index + 1}/{len(val_data)} images",
                    flush=True
                )

    intersection = confusion.diag().float()

    actual_pixels = confusion.sum(dim=1).float()
    predicted_pixels = confusion.sum(dim=0).float()

    union = actual_pixels + predicted_pixels - intersection

    iou = intersection / union.clamp(min=1)

    present_classes = union > 0

    miou = iou[present_classes].mean().item()

    pixel_accuracy = (
        intersection.sum() / actual_pixels.sum().clamp(min=1)
    ).item()

    print("\n========== LOVEDA EVALUATION ==========")

    print("Checkpoint best mIoU:", checkpoint["best_val_miou"])
    print("Validation mIoU:", round(miou, 4))
    print("Pixel Accuracy:", round(pixel_accuracy, 4))

    print("\nPer-class IoU:")

    for i, name in enumerate(CLASS_NAMES):
        if present_classes[i]:
            print(f"{name}: {iou[i].item():.4f}")
        else:
            print(f"{name}: Not present")

    print("\nConfusion Matrix:")
    print(confusion.numpy())

    print("\nEvaluation completed.")


if __name__ == "__main__":
    evaluate()
