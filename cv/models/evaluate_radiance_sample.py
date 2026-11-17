from pathlib import Path
import sys

import numpy as np
import rasterio
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = PROJECT_ROOT / "models" / "cv" / "radiance_sen1floods11_v2"

DATA_DIR = (
    PROJECT_ROOT
    / "data/raw/cv/flood/sen1floods11/sen1floods11_v1.1/data"
)

IMAGE_PATH = DATA_DIR / "S1GRDHand/Bolivia_103757_S1Hand.tif"
LABEL_PATH = DATA_DIR / "LabelHand/Bolivia_103757_LabelHand.tif"

sys.path.insert(0, str(MODEL_DIR))

from model import radiance_mae_vit_base, RadianceSegModel

MEAN = np.array([-12.577, -20.265], dtype=np.float32)
STD = np.array([5.176, 5.870], dtype=np.float32)

print("========== RADIANCE SAMPLE EVALUATION ==========")

# Load model and pretrained checkpoint
model = RadianceSegModel(radiance_mae_vit_base())

checkpoint = torch.load(
    MODEL_DIR / "best.pt",
    map_location="cpu",
    weights_only=True
)

model.load_state_dict(checkpoint["model"], strict=True)
model.eval()

# Read Sentinel-1 image
with rasterio.open(IMAGE_PATH) as src:
    sar = src.read([1, 2]).astype(np.float32)

# Read corresponding hand-labelled ground truth
with rasterio.open(LABEL_PATH) as src:
    labels = src.read(1)

# Verify matching dimensions
if sar.shape[1:] != labels.shape:
    raise ValueError("Image and label dimensions do not match.")

# Keep only pixels with finite SAR values
sar_valid = np.isfinite(sar).all(axis=0)

# Exclude unlabeled and unexpected label values
label_valid = np.isin(labels, [0, 1])

valid = sar_valid & label_valid

# Same centre crop as the inference smoke test
start = (512 - 224) // 2
end = start + 224

sar = sar[:, start:end, start:end]
labels = labels[start:end, start:end]
valid = valid[start:end, start:end]

# Apply the same preprocessing as the inference test
sar = np.nan_to_num(sar, nan=0.0, posinf=0.0, neginf=0.0)
sar = np.clip(sar, -60.0, 20.0)
sar = (sar - MEAN[:, None, None]) / STD[:, None, None]

input_tensor = torch.from_numpy(
    np.ascontiguousarray(sar)
).unsqueeze(0)

# Actual model inference
torch.set_num_threads(4)

with torch.inference_mode():
    logits = model(input_tensor)
    probabilities = torch.sigmoid(logits).squeeze().numpy()

if not np.isfinite(probabilities).all():
    raise RuntimeError("Non-finite predictions detected.")

# Evaluate only valid ground-truth pixels
y_true = labels[valid].astype(bool)

if y_true.size == 0:
    raise RuntimeError("No valid labelled pixels in centre crop.")

print("Image:", IMAGE_PATH.name)
print("Ground truth:", LABEL_PATH.name)
print("Evaluated pixels:", int(valid.sum()))
print("Ground-truth flood pixels:", int(y_true.sum()))
print("Ground-truth non-flood pixels:", int((~y_true).sum()))

for threshold in [0.25, 0.50]:
    y_pred = probabilities[valid] >= threshold

    tp = int(np.sum(y_pred & y_true))
    fp = int(np.sum(y_pred & ~y_true))
    fn = int(np.sum(~y_pred & y_true))
    tn = int(np.sum(~y_pred & ~y_true))

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )

    print(f"\n========== THRESHOLD {threshold} ==========")
    print("TP:", tp, "FP:", fp)
    print("FN:", fn, "TN:", tn)
    print("Precision:", round(precision, 4))
    print("Recall:", round(recall, 4))
    print("F1:", round(f1, 4))
    print("IoU:", round(iou, 4))

print("\nSAMPLE EVALUATION COMPLETE")
print("Training performed: NO")
print("Fine-tuning performed: NO")
