from __future__ import annotations

import argparse
import random
import threading
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import yaml
from PIL import Image
from torch.utils.data import DataLoader, Dataset


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "cv" / "configs" / "change.yaml"
DEFAULT_CHECKPOINT = ROOT / "models" / "cv" / "levir_cd_change" / "best.pt"
DEVICE = "cpu"


class ConvBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.block(x)


class SiameseEncoder(nn.Module):
    """Shared lightweight encoder for before/after RGB satellite images."""
    def __init__(self):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(3, 32, 3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
        )
        self.stage1 = nn.Sequential(
            ConvBlock(32, 32),
            nn.MaxPool2d(2),
        )
        self.stage2 = nn.Sequential(
            ConvBlock(32, 64),
            nn.MaxPool2d(2),
        )
        self.stage3 = nn.Sequential(
            ConvBlock(64, 128),
            nn.MaxPool2d(2),
        )
        self.stage4 = ConvBlock(128, 192)

    def forward(self, x):
        x1 = self.stem(x)       # 1/2
        x2 = self.stage1(x1)    # 1/4
        x3 = self.stage2(x2)    # 1/8
        x4 = self.stage3(x3)    # 1/16
        x5 = self.stage4(x4)    # 1/16
        return x1, x2, x3, x4, x5


class ChangeDecoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.deep = ConvBlock(192, 128)
        self.dec3 = ConvBlock(128 + 128, 96)
        self.dec2 = ConvBlock(96 + 64, 64)
        self.dec1 = ConvBlock(64 + 32, 48)
        self.head = nn.Sequential(
            ConvBlock(48, 32),
            nn.Conv2d(32, 1, kernel_size=1),
        )

    @staticmethod
    def upsample(x, reference):
        return F.interpolate(
            x, size=reference.shape[-2:],
            mode="bilinear", align_corners=False
        )

    def forward(self, differences, output_size):
        d1, d2, d3, d4, d5 = differences
        x = self.deep(d5)
        x = self.dec3(torch.cat([self.upsample(x, d4), d4], dim=1))
        x = self.dec2(torch.cat([self.upsample(x, d3), d3], dim=1))
        x = self.dec1(torch.cat([self.upsample(x, d2), d2], dim=1))
        x = F.interpolate(x, size=output_size, mode="bilinear", align_corners=False)
        return self.head(x)


class SiameseChangeDetector(nn.Module):
    """
    Binary change segmentation network.
    Inputs: before RGB tensor, after RGB tensor.
    Output: one-channel change logits.
    """
    def __init__(self):
        super().__init__()
        self.encoder = SiameseEncoder()
        self.decoder = ChangeDecoder()

    def forward(self, before, after):
        if before.shape != after.shape:
            raise ValueError(
                f"Paired images must have identical tensor shapes; "
                f"got {tuple(before.shape)} and {tuple(after.shape)}"
            )
        before_features = self.encoder(before)
        after_features = self.encoder(after)
        differences = [
            torch.abs(a - b)
            for a, b in zip(before_features, after_features)
        ]
        return self.decoder(differences, before.shape[-2:])


class LevirCDDataset(Dataset):
    """Expected split layout: split/A, split/B, split/label."""
    def __init__(self, root, split, image_size=256, limit=None, augment=False):
        self.root = Path(root)
        self.split = split
        self.image_size = int(image_size)
        self.augment = bool(augment)
        split_dir = self.root / split
        a_dir, b_dir, label_dir = (
            split_dir / "A", split_dir / "B", split_dir / "label"
        )
        if not all(p.is_dir() for p in (a_dir, b_dir, label_dir)):
            raise FileNotFoundError(
                f"Expected A, B and label folders under {split_dir}"
            )

        self.samples = []
        for a_path in sorted(a_dir.glob("*.png")):
            b_path = b_dir / a_path.name
            mask_path = label_dir / a_path.name
            if not b_path.is_file() or not mask_path.is_file():
                raise FileNotFoundError(
                    f"Missing paired file for {a_path.name}: "
                    f"B={b_path.is_file()}, label={mask_path.is_file()}"
                )
            self.samples.append((a_path, b_path, mask_path))

        if not self.samples:
            raise RuntimeError(f"No LEVIR-CD PNG pairs found in {split_dir}")

        if limit is not None and int(limit) > 0 and len(self.samples) > int(limit):
            rng = random.Random(42)
            self.samples = rng.sample(self.samples, int(limit))

    def __len__(self):
        return len(self.samples)

    @staticmethod
    def _read_rgb(path, size):
        with Image.open(path) as im:
            im = im.convert("RGB").resize(
                (size, size), Image.Resampling.BILINEAR
            )
            array = np.asarray(im, dtype=np.float32) / 255.0
        array = (array - 0.5) / 0.5
        return torch.from_numpy(array).permute(2, 0, 1).contiguous()

    def __getitem__(self, index):
        a_path, b_path, mask_path = self.samples[index]
        before = self._read_rgb(a_path, self.image_size)
        after = self._read_rgb(b_path, self.image_size)

        with Image.open(mask_path) as im:
            mask = im.convert("L").resize(
                (self.image_size, self.image_size),
                Image.Resampling.NEAREST,
            )
            mask = np.asarray(im if im.size == (self.image_size, self.image_size) else mask, dtype=np.uint8)

        # LEVIR-CD masks in this project were inspected as {0, 255}.
        # Treat every non-zero label pixel as changed.
        target = torch.from_numpy((mask > 0).astype(np.float32))[None, ...]

        if self.augment:
            if random.random() < 0.5:
                before = torch.flip(before, dims=[2])
                after = torch.flip(after, dims=[2])
                target = torch.flip(target, dims=[2])
            if random.random() < 0.5:
                before = torch.flip(before, dims=[1])
                after = torch.flip(after, dims=[1])
                target = torch.flip(target, dims=[1])

        return before, after, target


def combined_bce_dice_loss(logits, targets, dice_weight=0.5):
    bce = F.binary_cross_entropy_with_logits(logits, targets)
    probabilities = torch.sigmoid(logits)
    dims = (1, 2, 3)
    intersection = (probabilities * targets).sum(dim=dims)
    denominator = probabilities.sum(dim=dims) + targets.sum(dim=dims)
    dice = (2.0 * intersection + 1.0) / (denominator + 1.0)
    return bce + dice_weight * (1.0 - dice.mean())


@torch.no_grad()
def calculate_metrics(model, loader, threshold=0.5):
    model.eval()
    tp = fp = fn = tn = 0
    total_loss = 0.0
    batches = 0

    for before, after, target in loader:
        logits = model(before, after)
        total_loss += combined_bce_dice_loss(logits, target).item()
        batches += 1
        pred = torch.sigmoid(logits) >= threshold
        actual = target >= 0.5
        tp += int((pred & actual).sum())
        fp += int((pred & ~actual).sum())
        fn += int((~pred & actual).sum())
        tn += int((~pred & ~actual).sum())

    eps = 1e-8
    precision = tp / (tp + fp + eps)
    recall = tp / (tp + fn + eps)
    f1 = 2 * precision * recall / (precision + recall + eps)
    iou = tp / (tp + fp + fn + eps)
    return {
        "loss": total_loss / max(batches, 1),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "miou_change_class": iou,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    required = ("dataset_root", "image_size", "batch_size", "epochs")
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"Missing change config keys: {missing}")
    return config


def train_model(config):
    seed = int(config.get("seed", 42))
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(int(config.get("cpu_threads", 4)))

    dataset_root = ROOT / config["dataset_root"]
    train_set = LevirCDDataset(
        dataset_root, "train", config["image_size"],
        config.get("train_limit"), augment=True
    )
    val_set = LevirCDDataset(
        dataset_root, "val", config["image_size"],
        config.get("val_limit"), augment=False
    )
    train_loader = DataLoader(
        train_set, batch_size=int(config["batch_size"]),
        shuffle=True, num_workers=0
    )
    val_loader = DataLoader(
        val_set, batch_size=int(config["batch_size"]),
        shuffle=False, num_workers=0
    )

    model = SiameseChangeDetector().to(DEVICE)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config.get("learning_rate", 0.0003)),
        weight_decay=float(config.get("weight_decay", 0.0001)),
    )
    checkpoint = ROOT / config.get(
        "checkpoint", "models/cv/levir_cd_change/best.pt"
    )
    checkpoint.parent.mkdir(parents=True, exist_ok=True)

    best_iou = -1.0
    patience = int(config.get("early_stopping_patience", 2))
    stale_epochs = 0
    epochs = int(config["epochs"])

    print(f"Device: {DEVICE} | Parameters: {sum(p.numel() for p in model.parameters()):,}")
    print(f"Train pairs: {len(train_set)} | Validation pairs: {len(val_set)}")
    print(f"Image size: {config['image_size']} | Batch: {config['batch_size']}")

    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        batches = 0

        for before, after, target in train_loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model(before, after)
            loss = combined_bce_dice_loss(
                logits, target, float(config.get("dice_weight", 0.5))
            )
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
            batches += 1

        metrics = calculate_metrics(model, val_loader)
        train_loss = running_loss / max(batches, 1)
        print(
            f"Epoch {epoch}/{epochs} | "
            f"Train Loss: {train_loss:.4f} | "
            f"Val Loss: {metrics['loss']:.4f} | "
            f"Change IoU: {metrics['miou_change_class']:.4f} | "
            f"F1: {metrics['f1']:.4f} | "
            f"Precision: {metrics['precision']:.4f} | "
            f"Recall: {metrics['recall']:.4f}",
            flush=True,
        )

        score = metrics["miou_change_class"]
        if score > best_iou:
            best_iou = score
            stale_epochs = 0
            temp_path = checkpoint.with_suffix(".tmp")
            torch.save({
                "model_state_dict": model.state_dict(),
                "image_size": int(config["image_size"]),
                "threshold": float(config.get("threshold", 0.5)),
                "best_val_metrics": metrics,
                "epoch": epoch,
                "architecture": "SiameseChangeDetector",
            }, temp_path)
            temp_path.replace(checkpoint)
            print(f"Saved best checkpoint: {checkpoint}", flush=True)
        else:
            stale_epochs += 1
            if stale_epochs >= patience:
                print("Early stopping triggered.", flush=True)
                break

    print(f"Training finished. Best validation change IoU: {best_iou:.4f}")


class ChangeDetectionExecutor:
    """Lazy-loaded paired-image inference executor."""
    def __init__(self, checkpoint_path: Optional[str] = None):
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else DEFAULT_CHECKPOINT
        self.model = None
        self.image_size = 256
        self.threshold = 0.5
        self.lock = threading.Lock()

    def _load(self):
        if self.model is not None:
            return
        if not self.checkpoint_path.is_file() or self.checkpoint_path.stat().st_size == 0:
            raise FileNotFoundError(
                f"Change detection checkpoint is missing or empty: {self.checkpoint_path}"
            )
        checkpoint = torch.load(
            self.checkpoint_path, map_location=DEVICE, weights_only=False
        )
        model = SiameseChangeDetector()
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        self.image_size = int(checkpoint.get("image_size", 256))
        self.threshold = float(checkpoint.get("threshold", 0.5))
        self.model = model

    @staticmethod
    def _load_image(path, size):
        with Image.open(path) as im:
            original_size = im.size
            resized = im.convert("RGB").resize(
                (size, size), Image.Resampling.BILINEAR
            )
            array = np.asarray(resized, dtype=np.float32) / 255.0
        array = (array - 0.5) / 0.5
        tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0)
        return tensor, original_size

    def predict(self, image_path, second_image_path=None, output_dir=None,
                save_outputs=True, threshold=None, **kwargs):
        if not second_image_path:
            raise ValueError(
                "Change detection requires both image_path (before) "
                "and second_image_path (after)."
            )
        before_path = Path(image_path)
        after_path = Path(second_image_path)
        if not before_path.is_file() or not after_path.is_file():
            raise FileNotFoundError("Before or after satellite image was not found.")

        with self.lock, torch.no_grad():
            self._load()
            before, before_size = self._load_image(before_path, self.image_size)
            after, after_size = self._load_image(after_path, self.image_size)
            if before_size != after_size:
                raise ValueError(
                    f"Before/after image dimensions differ: {before_size} vs {after_size}"
                )
            probability = torch.sigmoid(self.model(before, after))[0, 0].numpy()
            selected_threshold = self.threshold if threshold is None else float(threshold)
            mask = (probability >= selected_threshold).astype(np.uint8)

        changed_pixels = int(mask.sum())
        total_pixels = int(mask.size)
        outputs = {}
        if save_outputs:
            if not output_dir:
                raise ValueError("output_dir is required when save_outputs=True.")
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            mask_path = out / "change_mask.png"
            probability_path = out / "change_probability.png"
            overlay_path = out / "change_overlay.png"

            original_w, original_h = before_size
            mask_image = Image.fromarray(mask * 255).resize(
                (original_w, original_h), Image.Resampling.NEAREST
            )
            prob_image = Image.fromarray(
                np.clip(probability * 255, 0, 255).astype(np.uint8)
            ).resize((original_w, original_h), Image.Resampling.BILINEAR)
            mask_image.save(mask_path)
            prob_image.save(probability_path)

            with Image.open(after_path) as im:
                base = np.asarray(im.convert("RGB"), dtype=np.uint8)
            overlay = base.copy()
            full_mask = np.asarray(mask_image) > 0
            tint = np.zeros_like(overlay)
            tint[..., 0] = 255
            overlay[full_mask] = (
                0.55 * overlay[full_mask] + 0.45 * tint[full_mask]
            ).astype(np.uint8)
            Image.fromarray(overlay).save(overlay_path)

            outputs = {
                "change_mask": str(mask_path),
                "change_probability": str(probability_path),
                "change_overlay": str(overlay_path),
            }

        return {
            "capability": "BUILDING_CHANGE",
            "model": "SiameseChangeDetector",
            "checkpoint": str(self.checkpoint_path),
            "before_image": str(before_path),
            "after_image": str(after_path),
            "image_width": int(before_size[0]),
            "image_height": int(before_size[1]),
            "changed_pixels_at_model_resolution": changed_pixels,
            "total_pixels_at_model_resolution": total_pixels,
            "changed_fraction_at_model_resolution": changed_pixels / total_pixels,
            "threshold": selected_threshold,
            "device": DEVICE,
            "training_performed": False,
            "outputs": outputs,
        }


_executor = ChangeDetectionExecutor()


def detect_building_changes(image_path, second_image_path=None, **kwargs):
    return _executor.predict(
        image_path=image_path,
        second_image_path=second_image_path,
        **kwargs,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Train the LEVIR-CD Siamese change detection model."
    )
    parser.add_argument("--config", default=str(CONFIG_PATH))
    args = parser.parse_args()
    config_path = Path(args.config)
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    train_model(config)


if __name__ == "__main__":
    main()
