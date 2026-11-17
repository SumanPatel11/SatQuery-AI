from pathlib import Path
import sys

import numpy as np
import rasterio
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_DIR = PROJECT_ROOT / "models" / "cv" / "radiance_sen1floods11_v2"

IMAGE_PATH = (
    PROJECT_ROOT
    / "data/raw/cv/flood/sen1floods11/sen1floods11_v1.1/data"
    / "S1GRDHand/Bolivia_103757_S1Hand.tif"
)

sys.path.insert(0, str(MODEL_DIR))

from model import radiance_mae_vit_base, RadianceSegModel

MEAN = np.array([-12.577, -20.265], dtype=np.float32)
STD = np.array([5.176, 5.870], dtype=np.float32)

DEVICE = torch.device("cpu")

print("========== RADIANCE FLOOD INFERENCE ==========")

# 1. Load model architecture
encoder = radiance_mae_vit_base()
model = RadianceSegModel(encoder)

# 2. Load verified pretrained checkpoint
checkpoint = torch.load(
    MODEL_DIR / "best.pt",
    map_location="cpu",
    weights_only=True
)

model.load_state_dict(checkpoint["model"], strict=True)
model.to(DEVICE)
model.eval()

print("Checkpoint loaded successfully.")

# 3. Read actual Sentinel-1 image
with rasterio.open(IMAGE_PATH) as src:
    sar = src.read([1, 2]).astype(np.float32)
    print("Image:", IMAGE_PATH.name)
    print("Original shape:", sar.shape)

# 4. Preserve original valid-pixel information
valid_mask = np.isfinite(sar).all(axis=0)
print("Valid pixel percentage:", round(float(valid_mask.mean() * 100), 2))

# 5. Apply official preprocessing
sar = np.nan_to_num(
    sar,
    nan=0.0,
    posinf=0.0,
    neginf=0.0
)

sar = np.clip(sar, -60.0, 20.0)
sar = (sar - MEAN[:, None, None]) / STD[:, None, None]

# 6. Take 224 x 224 centre crop
start = (512 - 224) // 2

sar = sar[
    :,
    start:start + 224,
    start:start + 224
]

valid_crop = valid_mask[
    start:start + 224,
    start:start + 224
]

if sar.shape != (2, 224, 224):
    raise ValueError(f"Unexpected input shape: {sar.shape}")

input_tensor = torch.from_numpy(
    np.ascontiguousarray(sar)
).unsqueeze(0).to(DEVICE)

print("Model input shape:", tuple(input_tensor.shape))

# 7. Actual inference
torch.set_num_threads(4)

with torch.inference_mode():
    logits = model(input_tensor)
    probabilities = torch.sigmoid(logits).squeeze(0).squeeze(0)

probabilities = probabilities.cpu().numpy()

if probabilities.shape != (224, 224):
    raise RuntimeError(f"Unexpected output shape: {probabilities.shape}")

if not np.isfinite(probabilities).all():
    raise RuntimeError("Non-finite predictions detected.")

# 8. Report actual model output
valid_probabilities = probabilities[valid_crop]

if valid_probabilities.size == 0:
    raise RuntimeError("No valid pixels in the selected crop.")

print("\n========== ACTUAL MODEL OUTPUT ==========")
print("Output shape:", probabilities.shape)
print("Probability minimum:", float(valid_probabilities.min()))
print("Probability maximum:", float(valid_probabilities.max()))
print("Probability mean:", float(valid_probabilities.mean()))

for threshold in [0.25, 0.50]:
    predicted_flood = valid_probabilities >= threshold
    flood_pixels = int(predicted_flood.sum())
    flood_percentage = float(predicted_flood.mean() * 100)

    print(f"\nThreshold: {threshold}")
    print("Predicted flood pixels:", flood_pixels)
    print("Predicted flood percentage:", round(flood_percentage, 2))

print("\nINFERENCE TEST: SUCCESS")
print("Training performed: NO")
print("Fine-tuning performed: NO")
