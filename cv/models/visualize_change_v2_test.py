from __future__ import annotations

import argparse
from pathlib import Path

import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from torch.utils.data import DataLoader

from cv.models.change_v2 import LevirCDDataset, SiameseAttentionChangeNet


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHECKPOINT = PROJECT_ROOT / "models/cv/levir_cd_change_v2/best.pt"
DEFAULT_DATASET = PROJECT_ROOT / "data/raw/cv/change/levir_cd"


def tensor_to_rgb(tensor):
    arr = tensor.detach().cpu().float().permute(1, 2, 0).numpy()
    arr = np.nan_to_num(arr)
    if arr.min() < 0.0:
        arr = (arr * 0.5) + 0.5
    arr = arr * 255.0
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode="RGB")


def mask_to_l(tensor):
    arr = tensor.detach().cpu().squeeze().numpy()
    arr = np.clip(arr, 0, 1)
    return Image.fromarray((arr * 255).astype(np.uint8), mode="L")


def make_overlay(after_img, pred_mask):
    base = np.asarray(after_img.convert("RGB")).astype(np.float32)
    mask = np.asarray(pred_mask).astype(bool)
    overlay = base.copy()
    # Red highlights are a visualization convention, not model output values.
    red = np.zeros_like(base)
    red[..., 0] = 255
    overlay[mask] = 0.55 * base[mask] + 0.45 * red[mask]
    return Image.fromarray(np.clip(overlay, 0, 255).astype(np.uint8), "RGB")


def add_label(image, label, height=26):
    panel = Image.new("RGB", (image.width, image.height + height), "white")
    panel.paste(image, (0, height))
    draw = ImageDraw.Draw(panel)
    draw.text((8, 6), label, fill="black")
    return panel


@torch.no_grad()
def main():
    parser = argparse.ArgumentParser(
        description="Create visual comparisons for V2 on LEVIR-CD test samples."
    )
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--dataset-root", default=str(DEFAULT_DATASET))
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--threads", type=int, default=6)
    args = parser.parse_args()

    checkpoint_path = Path(args.checkpoint)
    if not checkpoint_path.is_file() or checkpoint_path.stat().st_size == 0:
        raise FileNotFoundError(f"Checkpoint missing or empty: {checkpoint_path}")

    torch.set_num_threads(args.threads)
    device = torch.device("cpu")
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)

    model = SiameseAttentionChangeNet().to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    threshold = float(checkpoint.get("threshold", 0.5))
    image_size = int(checkpoint.get("image_size", 256))
    dataset = LevirCDDataset(
        Path(args.dataset_root), "test", image_size=image_size, augment=False
    )
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, num_workers=0)

    output_dir = checkpoint_path.parent / "test_visuals"
    output_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for before, after, target in loader:
        before = before.to(device)
        after = after.to(device)
        logits = model(before, after)
        probabilities = torch.sigmoid(logits)
        predictions = probabilities >= threshold

        for i in range(before.shape[0]):
            if saved >= args.count:
                break
            before_img = tensor_to_rgb(before[i])
            after_img = tensor_to_rgb(after[i])
            gt_img = mask_to_l(target[i])
            pred_img = mask_to_l(predictions[i].float())
            overlay_img = make_overlay(after_img, np.asarray(pred_img) > 127)

            panels = [
                add_label(before_img, "Before (A)"),
                add_label(after_img, "After (B)"),
                add_label(gt_img.convert("RGB"), "Ground truth"),
                add_label(pred_img.convert("RGB"), f"Prediction (threshold {threshold:.2f})"),
                add_label(overlay_img, "Prediction overlay (red = predicted change)"),
            ]
            width = sum(p.width for p in panels)
            height = max(p.height for p in panels)
            canvas = Image.new("RGB", (width, height), "#dddddd")
            x = 0
            for panel in panels:
                canvas.paste(panel, (x, 0))
                x += panel.width

            out_file = output_dir / f"test_sample_{saved + 1:02d}.png"
            canvas.save(out_file)
            saved += 1

        if saved >= args.count:
            break

    print(f"Checkpoint epoch: {checkpoint.get('epoch', 'unknown')}")
    print(f"Threshold from validation: {threshold:.2f}")
    print(f"Saved {saved} visual comparisons to: {output_dir}")
    print("No test threshold tuning or checkpoint modification was performed.")


if __name__ == "__main__":
    main()

