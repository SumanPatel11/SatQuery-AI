from pathlib import Path
import argparse
import random
import threading

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import yaml

from PIL import Image
from torch.utils.data import Dataset, DataLoader
from torchvision.models import mobilenet_v3_small


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "cv/configs/land_cover.yaml"
CHECKPOINT = ROOT / "models/cv/loveda_land_cover/best.pt"
OUTPUT_DIR = ROOT / "cv/outputs/predictions/land_cover"

CLASS_NAMES = [
    "background", "building", "road", "water",
    "barren", "forest", "agriculture"
]

IGNORE_INDEX = 255
DEVICE = "cpu"


class LoveDADataset(Dataset):

    def __init__(self, root, split, image_size, limit=None):
        self.samples = []
        self.image_size = image_size

        for area in ("Urban", "Rural"):
            base = Path(root) / split / area
            image_dir = base / "images_png"
            mask_dir = base / "masks_png"

            for image_path in sorted(image_dir.glob("*.png")):
                mask_path = mask_dir / image_path.name
                if not mask_path.is_file():
                    raise FileNotFoundError(mask_path)
                self.samples.append((image_path, mask_path))

        if limit is not None:
            random.Random(42).shuffle(self.samples)
            self.samples = self.samples[:limit]

        if not self.samples:
            raise RuntimeError(f"No images found for {split}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        image_path, mask_path = self.samples[index]

        with Image.open(image_path) as im:
            image = im.convert("RGB").resize(
                (self.image_size, self.image_size),
                Image.Resampling.BILINEAR
            )
            image = np.asarray(image, dtype=np.float32) / 255.0

        with Image.open(mask_path) as im:
            mask = im.resize(
                (self.image_size, self.image_size),
                Image.Resampling.NEAREST
            )
            mask = np.asarray(mask, dtype=np.uint8)

        if not np.isin(mask, np.arange(8)).all():
            raise ValueError(f"Unexpected mask IDs in {mask_path}")

        target = np.full(mask.shape, IGNORE_INDEX, dtype=np.int64)
        valid = mask != 0
        target[valid] = mask[valid].astype(np.int64) - 1

        image = torch.from_numpy(image).permute(2, 0, 1).contiguous()
        return image, torch.from_numpy(target)


class ConvBlock(nn.Module):

    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x):
        return self.block(x)


class LoveDASegmenter(nn.Module):

    def __init__(self, num_classes=7):
        super().__init__()

        features = mobilenet_v3_small(weights=None).features

        self.enc1 = nn.Sequential(*features[:2])
        self.enc2 = nn.Sequential(*features[2:4])
        self.enc3 = nn.Sequential(*features[4:9])
        self.enc4 = nn.Sequential(*features[9:])

        self.dec3 = ConvBlock(576 + 48, 64)
        self.dec2 = ConvBlock(64 + 24, 32)
        self.dec1 = ConvBlock(32 + 16, 24)

        self.classifier = nn.Conv2d(24, num_classes, 1)

    def forward(self, x):
        size = x.shape[-2:]

        e1 = self.enc1(x)
        e2 = self.enc2(e1)
        e3 = self.enc3(e2)
        e4 = self.enc4(e3)

        x = F.interpolate(e4, size=e3.shape[-2:], mode="bilinear",
                          align_corners=False)
        x = self.dec3(torch.cat([x, e3], dim=1))

        x = F.interpolate(x, size=e2.shape[-2:], mode="bilinear",
                          align_corners=False)
        x = self.dec2(torch.cat([x, e2], dim=1))

        x = F.interpolate(x, size=e1.shape[-2:], mode="bilinear",
                          align_corners=False)
        x = self.dec1(torch.cat([x, e1], dim=1))

        x = F.interpolate(x, size=size, mode="bilinear",
                          align_corners=False)
        return self.classifier(x)


def calculate_miou(predictions, targets):
    scores = []

    for class_id in range(7):
        pred = predictions == class_id
        actual = targets == class_id
        union = (pred | actual).sum().item()

        if union:
            intersection = (pred & actual).sum().item()
            scores.append(intersection / union)

    return float(np.mean(scores)) if scores else 0.0


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    required = [
        "dataset_root", "image_size", "batch_size",
        "epochs", "train_limit", "val_limit"
    ]

    for key in required:
        if key not in config:
            raise ValueError(f"Missing config: {key}")

    return config


def train_model(config):
    torch.set_num_threads(config.get("cpu_threads", 6))
    torch.manual_seed(config.get("seed", 42))
    np.random.seed(config.get("seed", 42))
    random.seed(config.get("seed", 42))

    dataset_root = ROOT / config["dataset_root"]

    train_data = LoveDADataset(
        dataset_root, "Train",
        config["image_size"], config["train_limit"]
    )
    val_data = LoveDADataset(
        dataset_root, "Val",
        config["image_size"], config["val_limit"]
    )

    train_loader = DataLoader(
        train_data, batch_size=config["batch_size"],
        shuffle=True, num_workers=0
    )
    val_loader = DataLoader(
        val_data, batch_size=config["batch_size"],
        shuffle=False, num_workers=0
    )

    model = LoveDASegmenter().to(DEVICE)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.get("learning_rate", 0.0003)
    )
    criterion = nn.CrossEntropyLoss(ignore_index=IGNORE_INDEX)

    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    best_miou = -1.0

    for epoch in range(config["epochs"]):
        model.train()
        train_loss = 0.0

        for images, masks in train_loader:
            images, masks = images.to(DEVICE), masks.to(DEVICE)

            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = criterion(logits, masks)
            loss.backward()
            optimizer.step()

            train_loss += loss.item()

        model.eval()
        val_loss = 0.0
        predictions_all = []
        targets_all = []

        with torch.no_grad():
            for images, masks in val_loader:
                images, masks = images.to(DEVICE), masks.to(DEVICE)
                logits = model(images)
                val_loss += criterion(logits, masks).item()

                predictions = logits.argmax(dim=1)
                valid = masks != IGNORE_INDEX

                predictions_all.append(predictions[valid].cpu())
                targets_all.append(masks[valid].cpu())

        miou = calculate_miou(
            torch.cat(predictions_all),
            torch.cat(targets_all)
        )

        train_loss /= len(train_loader)
        val_loss /= len(val_loader)

        print(
            f"Epoch {epoch + 1}/{config['epochs']} | "
            f"Train Loss: {train_loss:.4f} | "
            f"Val Loss: {val_loss:.4f} | mIoU: {miou:.4f}",
            flush=True
        )

        if miou > best_miou:
            best_miou = miou
            torch.save({
                "model_state_dict": model.state_dict(),
                "num_classes": 7,
                "image_size": config["image_size"],
                "class_names": CLASS_NAMES,
                "best_val_miou": best_miou
            }, CHECKPOINT)

            print("Best checkpoint saved:", CHECKPOINT)

    print("Training completed.")
    print("Best validation mIoU:", best_miou)


class LandCoverPredictor:

    def __init__(self):
        self._model = None
        self._lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def _load_model(self):
        if self._model is not None:
            return self._model

        with self._lock:
            if self._model is None:
                if not CHECKPOINT.is_file():
                    raise FileNotFoundError(CHECKPOINT)

                checkpoint = torch.load(
                    CHECKPOINT, map_location=DEVICE,
                    weights_only=False
                )

                model = LoveDASegmenter(checkpoint["num_classes"])
                model.load_state_dict(checkpoint["model_state_dict"])
                model.eval()
                self._model = model

        return self._model

    def predict(self, image_path, output_dir=None, save_outputs=True):
        image_path = Path(image_path)

        if not image_path.is_file():
            raise FileNotFoundError(image_path)

        with Image.open(image_path) as im:
            original = im.convert("RGB")
            original_size = original.size
            resized = original.resize(
                (256, 256), Image.Resampling.BILINEAR
            )
            array = np.asarray(resized, dtype=np.float32) / 255.0

        tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0)
        model = self._load_model()

        with self._inference_lock, torch.no_grad():
            prediction = model(tensor).argmax(dim=1)[0].numpy()

        prediction = Image.fromarray(prediction.astype(np.uint8))
        prediction = prediction.resize(
            original_size, Image.Resampling.NEAREST
        )
        prediction = np.asarray(prediction, dtype=np.uint8)

        counts = {
            CLASS_NAMES[i]: int(np.count_nonzero(prediction == i))
            for i in range(7)
        }

        outputs = {}

        if save_outputs:
            destination = Path(output_dir) if output_dir else OUTPUT_DIR
            destination.mkdir(parents=True, exist_ok=True)
            mask_path = destination / f"{image_path.stem}_landcover.png"
            Image.fromarray(prediction).save(mask_path)
            outputs["segmentation_mask"] = str(mask_path)

        return {
            "capability": "LAND_COVER_DETECTION",
            "model": "LoveDA MobileNetV3 Small U-Net",
            "checkpoint": str(CHECKPOINT),
            "input": str(image_path),
            "image_width": original_size[0],
            "image_height": original_size[1],
            "class_pixel_counts": counts,
            "device": DEVICE,
            "training_performed": False,
            "outputs": outputs
        }


_predictor = LandCoverPredictor()


def detect_land_cover(image_path, **kwargs):
    return _predictor.predict(image_path, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--start", action="store_true",
        help="Explicitly start LoveDA pilot training"
    )
    args = parser.parse_args()

    config = load_config()

    print("LoveDA configuration:")
    for key, value in config.items():
        print(f"{key}: {value}")

    if not args.start:
        print("Training NOT started. Use --start when approved.")
        return

    train_model(config)


if __name__ == "__main__":
    main()
