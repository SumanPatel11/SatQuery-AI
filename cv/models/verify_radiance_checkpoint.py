from pathlib import Path
import sys
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = PROJECT_ROOT / "models" / "cv" / "radiance_sen1floods11_v2"

sys.path.insert(0, str(MODEL_DIR))

from model import radiance_mae_vit_base, RadianceSegModel

checkpoint_path = MODEL_DIR / "best.pt"

print("Loading Radiance architecture...")
encoder = radiance_mae_vit_base()
model = RadianceSegModel(encoder)

print("Loading checkpoint...")
checkpoint = torch.load(
    checkpoint_path,
    map_location="cpu",
    weights_only=True
)

if "model" not in checkpoint:
    raise KeyError("Checkpoint does not contain model state dictionary.")

result = model.load_state_dict(
    checkpoint["model"],
    strict=True
)

print("\nSTRICT CHECKPOINT LOADING: SUCCESS")
print("Missing keys:", result.missing_keys)
print("Unexpected keys:", result.unexpected_keys)
print("Checkpoint epoch:", checkpoint.get("epoch"))
print("Checkpoint metrics:", checkpoint.get("metrics"))

model.eval()

print("Model mode: EVAL")
print("Device: CPU")
