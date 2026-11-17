from __future__ import annotations

import argparse
import random
import threading
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import yaml
from PIL import Image
from torch.utils.data import DataLoader, Dataset


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "cv" / "configs" / "change_v2.yaml"
DEVICE = "cpu"


class ResidualBlock(nn.Module):
    def __init__(self, in_channels, out_channels, stride=1):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, 3, stride, 1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.conv2 = nn.Conv2d(out_channels, out_channels, 3, 1, 1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)
        self.skip = (
            nn.Identity()
            if stride == 1 and in_channels == out_channels
            else nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 1, stride, bias=False),
                nn.BatchNorm2d(out_channels),
            )
        )

    def forward(self, x):
        residual = self.skip(x)
        x = F.relu(self.bn1(self.conv1(x)), inplace=True)
        x = self.bn2(self.conv2(x))
        return F.relu(x + residual, inplace=True)


class SharedEncoder(nn.Module):
    """Residual Siamese encoder; weights are shared across dates."""
    def __init__(self):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(3, 32, 3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
        )
        self.s1 = nn.Sequential(ResidualBlock(32, 32), ResidualBlock(32, 32))
        self.s2 = nn.Sequential(ResidualBlock(32, 64, 2), ResidualBlock(64, 64))
        self.s3 = nn.Sequential(ResidualBlock(64, 128, 2), ResidualBlock(128, 128))
        self.s4 = nn.Sequential(ResidualBlock(128, 192, 2), ResidualBlock(192, 192))
        self.s5 = nn.Sequential(ResidualBlock(192, 256, 2), ResidualBlock(256, 256))

    def forward(self, x):
        x = self.stem(x)
        f1 = self.s1(x)       # 1/2
        f2 = self.s2(f1)      # 1/4
        f3 = self.s3(f2)      # 1/8
        f4 = self.s4(f3)      # 1/16
        f5 = self.s5(f4)      # 1/32
        return f1, f2, f3, f4, f5


class AttentionGate(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.gate = nn.Sequential(
            nn.Conv2d(channels, channels, 1, bias=False),
            nn.BatchNorm2d(channels),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return x * self.gate(x)


class DecoderBlock(nn.Module):
    def __init__(self, in_channels, skip_channels, out_channels):
        super().__init__()
        self.fuse = nn.Sequential(
            ResidualBlock(in_channels + skip_channels, out_channels),
            ResidualBlock(out_channels, out_channels),
        )
        self.attention = AttentionGate(out_channels)

    def forward(self, x, skip):
        x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        x = self.fuse(torch.cat([x, skip], dim=1))
        return self.attention(x)


class SiameseAttentionChangeNet(nn.Module):
    """
    Siamese residual U-Net with multi-level temporal feature fusion.
    For each scale, fusion is [abs(before-after), before*after].
    """
    def __init__(self):
        super().__init__()
        self.encoder = SharedEncoder()
        self.deep = nn.Sequential(
            ResidualBlock(512, 256),
            ResidualBlock(256, 256),
        )
        self.dec4 = DecoderBlock(256, 384, 192)
        self.dec3 = DecoderBlock(192, 256, 128)
        self.dec2 = DecoderBlock(128, 128, 64)
        self.dec1 = DecoderBlock(64, 64, 32)
        self.head = nn.Sequential(
            ResidualBlock(32, 32),
            nn.Conv2d(32, 1, 1),
        )

    @staticmethod
    def temporal_fusion(a, b):
        return torch.cat([torch.abs(a - b), a * b], dim=1)

    def forward(self, before, after):
        if before.shape != after.shape:
            raise ValueError("Before and after tensors must have identical shapes.")
        fa = self.encoder(before)
        fb = self.encoder(after)
        fused = [self.temporal_fusion(a, b) for a, b in zip(fa, fb)]
        x = self.deep(fused[4])
        x = self.dec4(x, fused[3])
        x = self.dec3(x, fused[2])
        x = self.dec2(x, fused[1])
        x = self.dec1(x, fused[0])
        x = F.interpolate(x, size=before.shape[-2:], mode="bilinear", align_corners=False)
        return self.head(x)


class LevirCDDataset(Dataset):
    def __init__(self, root, split, image_size=256, augment=False):
        self.root = Path(root)
        self.image_size = int(image_size)
        self.augment = bool(augment)
        folder = self.root / split
        a_dir, b_dir, mask_dir = folder / "A", folder / "B", folder / "label"
        if not all(p.is_dir() for p in (a_dir, b_dir, mask_dir)):
            raise FileNotFoundError(f"Expected A/B/label directories in {folder}")
        self.samples = []
        for a in sorted(a_dir.glob("*.png")):
            b, m = b_dir / a.name, mask_dir / a.name
            if not b.is_file() or not m.is_file():
                raise FileNotFoundError(f"Unmatched LEVIR-CD triplet: {a.name}")
            self.samples.append((a, b, m))
        if not self.samples:
            raise RuntimeError(f"No image triplets found in {folder}")

    def __len__(self):
        return len(self.samples)

    def _rgb(self, path):
        with Image.open(path) as im:
            im = im.convert("RGB").resize(
                (self.image_size, self.image_size), Image.Resampling.BILINEAR
            )
            arr = np.asarray(im, dtype=np.float32) / 255.0
        arr = (arr - 0.5) / 0.5
        return torch.from_numpy(arr).permute(2, 0, 1).contiguous()

    def __getitem__(self, idx):
        a_path, b_path, mask_path = self.samples[idx]
        before, after = self._rgb(a_path), self._rgb(b_path)
        with Image.open(mask_path) as im:
            im = im.convert("L").resize(
                (self.image_size, self.image_size), Image.Resampling.NEAREST
            )
            mask = np.asarray(im, dtype=np.uint8)
        target = torch.from_numpy((mask > 0).astype(np.float32))[None]

        if self.augment:
            # Same geometric transform is applied to both dates and the mask.
            if random.random() < 0.5:
                before, after, target = (
                    torch.flip(before, [2]), torch.flip(after, [2]), torch.flip(target, [2])
                )
            if random.random() < 0.5:
                before, after, target = (
                    torch.flip(before, [1]), torch.flip(after, [1]), torch.flip(target, [1])
                )
            k = random.randrange(4)
            if k:
                before = torch.rot90(before, k, [1, 2])
                after = torch.rot90(after, k, [1, 2])
                target = torch.rot90(target, k, [1, 2])
        return before, after, target


def loss_fn(logits, target, pos_weight=4.0, dice_weight=0.7):
    weight = torch.tensor([float(pos_weight)], dtype=logits.dtype, device=logits.device)
    bce = F.binary_cross_entropy_with_logits(logits, target, pos_weight=weight)
    prob = torch.sigmoid(logits)
    dims = (1, 2, 3)
    intersection = (prob * target).sum(dims)
    denominator = prob.sum(dims) + target.sum(dims)
    dice = (2 * intersection + 1.0) / (denominator + 1.0)
    return bce + float(dice_weight) * (1.0 - dice.mean())


@torch.no_grad()
def evaluate(model, loader, thresholds, pos_weight, dice_weight):
    model.eval()
    all_prob, all_target = [], []
    loss_total, batches = 0.0, 0
    for before, after, target in loader:
        logits = model(before, after)
        loss_total += loss_fn(logits, target, pos_weight, dice_weight).item()
        batches += 1
        all_prob.append(torch.sigmoid(logits).cpu())
        all_target.append(target.cpu())

    probs = torch.cat(all_prob, dim=0)
    targets = torch.cat(all_target, dim=0) >= 0.5
    best = None
    eps = 1e-8
    for threshold in thresholds:
        pred = probs >= float(threshold)
        tp = int((pred & targets).sum())
        fp = int((pred & ~targets).sum())
        fn = int((~pred & targets).sum())
        precision = tp / (tp + fp + eps)
        recall = tp / (tp + fn + eps)
        f1 = 2 * precision * recall / (precision + recall + eps)
        iou = tp / (tp + fp + fn + eps)
        candidate = {
            "threshold": float(threshold),
            "loss": loss_total / max(batches, 1),
            "change_iou": iou,
            "f1": f1,
            "precision": precision,
            "recall": recall,
            "tp": tp, "fp": fp, "fn": fn,
        }
        if best is None or candidate["change_iou"] > best["change_iou"]:
            best = candidate
    return best


def train(config):
    seed = int(config.get("seed", 42))
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(int(config.get("cpu_threads", 6)))

    root = ROOT / config["dataset_root"]
    train_set = LevirCDDataset(root, "train", config["image_size"], augment=True)
    val_set = LevirCDDataset(root, "val", config["image_size"], augment=False)
    train_loader = DataLoader(
        train_set, batch_size=int(config["batch_size"]), shuffle=True, num_workers=0
    )
    val_loader = DataLoader(
        val_set, batch_size=int(config["batch_size"]), shuffle=False, num_workers=0
    )

    model = SiameseAttentionChangeNet().to(DEVICE)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=float(config["learning_rate"]),
        weight_decay=float(config["weight_decay"])
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", factor=0.5, patience=1
    )
    thresholds = [round(x, 2) for x in np.arange(0.20, 0.71, 0.05)]
    checkpoint = ROOT / config["checkpoint"]
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    best_iou, stale = -1.0, 0
    patience = int(config["early_stopping_patience"])
    epochs = int(config["epochs"])
    print(
        f"Device: {DEVICE} | Parameters: {sum(p.numel() for p in model.parameters()):,}",
        flush=True
    )
    print(
        f"Train pairs: {len(train_set)} | Validation pairs: {len(val_set)} | "
        f"Image size: {config['image_size']} | Batch: {config['batch_size']}",
        flush=True
    )

    for epoch in range(1, epochs + 1):
        model.train()
        running, steps = 0.0, 0
        for before, after, target in train_loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model(before, after)
            loss = loss_fn(
                logits, target, config["positive_weight"], config["dice_weight"]
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            running += loss.item()
            steps += 1

        metrics = evaluate(
            model, val_loader, thresholds,
            config["positive_weight"], config["dice_weight"]
        )
        scheduler.step(metrics["change_iou"])
        print(
            f"Epoch {epoch}/{epochs} | Train Loss: {running/max(steps,1):.4f} | "
            f"Val Loss: {metrics['loss']:.4f} | Change IoU: {metrics['change_iou']:.4f} | "
            f"F1: {metrics['f1']:.4f} | Precision: {metrics['precision']:.4f} | "
            f"Recall: {metrics['recall']:.4f} | Selected threshold: {metrics['threshold']:.2f}",
            flush=True
        )

        if metrics["change_iou"] > best_iou:
            best_iou, stale = metrics["change_iou"], 0
            temp = checkpoint.with_suffix(".tmp")
            torch.save({
                "model_state_dict": model.state_dict(),
                "image_size": int(config["image_size"]),
                "threshold": metrics["threshold"],
                "best_val_metrics": metrics,
                "epoch": epoch,
                "architecture": "SiameseAttentionChangeNet",
            }, temp)
            temp.replace(checkpoint)
            print(f"Saved V2 best checkpoint: {checkpoint}", flush=True)
        else:
            stale += 1
            if stale >= patience:
                print("V2 early stopping triggered.", flush=True)
                break

    print(f"V2 finished. Best validation change IoU: {best_iou:.4f}", flush=True)


class ChangeDetectionV2Executor:
    def __init__(self, checkpoint_path=None):
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else (
            ROOT / "models/cv/levir_cd_change_v2/best.pt"
        )
        self.model = None
        self.image_size = 256
        self.threshold = 0.5
        self.lock = threading.Lock()

    def _load(self):
        if self.model is not None:
            return
        if not self.checkpoint_path.is_file() or self.checkpoint_path.stat().st_size == 0:
            raise FileNotFoundError(f"V2 checkpoint not found: {self.checkpoint_path}")
        ckpt = torch.load(self.checkpoint_path, map_location=DEVICE, weights_only=False)
        model = SiameseAttentionChangeNet()
        model.load_state_dict(ckpt["model_state_dict"])
        model.eval()
        self.image_size = int(ckpt.get("image_size", 256))
        self.threshold = float(ckpt.get("threshold", 0.5))
        self.model = model

    def predict(self, image_path, second_image_path=None, output_dir=None,
                save_outputs=True, threshold=None, **kwargs):
        if not second_image_path:
            raise ValueError("V2 change detection requires before and after images.")
        before_path, after_path = Path(image_path), Path(second_image_path)
        if not before_path.is_file() or not after_path.is_file():
            raise FileNotFoundError("Before/after image path does not exist.")
        with self.lock, torch.no_grad():
            self._load()
            def load(path):
                with Image.open(path) as im:
                    size = im.size
                    im = im.convert("RGB").resize(
                        (self.image_size, self.image_size), Image.Resampling.BILINEAR
                    )
                    arr = np.asarray(im, dtype=np.float32) / 255.0
                arr = (arr - 0.5) / 0.5
                return torch.from_numpy(arr).permute(2,0,1).unsqueeze(0), size
            before, size_a = load(before_path)
            after, size_b = load(after_path)
            if size_a != size_b:
                raise ValueError(f"Input image dimensions differ: {size_a} vs {size_b}")
            prob = torch.sigmoid(self.model(before, after))[0,0].numpy()
            used_threshold = self.threshold if threshold is None else float(threshold)
            mask = (prob >= used_threshold).astype(np.uint8)

        outputs = {}
        if save_outputs:
            if not output_dir:
                raise ValueError("output_dir is required when save_outputs=True.")
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            w, h = size_a
            mask_img = Image.fromarray(mask * 255).resize((w,h), Image.Resampling.NEAREST)
            prob_img = Image.fromarray(np.clip(prob*255,0,255).astype(np.uint8)).resize(
                (w,h), Image.Resampling.BILINEAR
            )
            with Image.open(after_path) as im:
                overlay = np.asarray(im.convert("RGB"), dtype=np.uint8).copy()
            m = np.asarray(mask_img) > 0
            overlay[m] = (0.55*overlay[m] + 0.45*np.array([255,0,0])).astype(np.uint8)
            mask_path, prob_path, overlay_path = (
                out/"change_mask.png", out/"change_probability.png", out/"change_overlay.png"
            )
            mask_img.save(mask_path)
            prob_img.save(prob_path)
            Image.fromarray(overlay).save(overlay_path)
            outputs = {
                "change_mask": str(mask_path),
                "change_probability": str(prob_path),
                "change_overlay": str(overlay_path),
            }

        changed = int(mask.sum())
        return {
            "capability": "BUILDING_CHANGE",
            "model": "SiameseAttentionChangeNet",
            "before_image": str(before_path),
            "after_image": str(after_path),
            "image_width": size_a[0],
            "image_height": size_a[1],
            "changed_pixels_at_model_resolution": changed,
            "total_pixels_at_model_resolution": int(mask.size),
            "changed_fraction_at_model_resolution": changed / int(mask.size),
            "threshold": used_threshold,
            "device": DEVICE,
            "outputs": outputs,
        }


_executor = ChangeDetectionV2Executor()


def detect_building_changes(image_path, second_image_path=None, **kwargs):
    return _executor.predict(
        image_path=image_path, second_image_path=second_image_path, **kwargs
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(CONFIG_PATH))
    args = parser.parse_args()
    with Path(args.config).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    train(config)


if __name__ == "__main__":
    main()
