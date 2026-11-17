
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]

original_path = ROOT / "data/raw/cv/land_cover/loveda/Val/Rural/images_png/2522.png"
mask_path = ROOT / "data/raw/cv/land_cover/loveda/Val/Rural/masks_png/2522.png"
prediction_path = ROOT / "cv/outputs/predictions/land_cover/2522_landcover.png"

output_path = ROOT / "cv/outputs/predictions/land_cover/2522_comparison.png"

names = [
    "Background", "Building", "Road", "Water",
    "Barren", "Forest", "Agriculture"
]

palette = np.array([
    [0, 0, 0],
    [220, 50, 50],
    [255, 150, 40],
    [40, 120, 255],
    [180, 130, 80],
    [30, 150, 70],
    [150, 200, 50],
])

original = Image.open(original_path).convert("RGB")
gt_raw = np.array(Image.open(mask_path), dtype=np.uint8)
pred = np.array(Image.open(prediction_path), dtype=np.uint8)

# LoveDA raw IDs 1-7 map to model IDs 0-6.
gt = np.full(gt_raw.shape, 255, dtype=np.uint8)
valid = gt_raw > 0
gt[valid] = gt_raw[valid] - 1

def colorize(mask):
    rgb = np.zeros((*mask.shape, 3), dtype=np.uint8)
    valid = mask < 7
    rgb[valid] = palette[mask[valid]]
    return Image.fromarray(rgb)

gt_color = colorize(gt)
pred_color = colorize(pred)

overlay = Image.blend(
    gt_color.convert("RGB"),
    pred_color.convert("RGB"),
    0.5
)

# Create comparison canvas
panel_size = (512, 512)
canvas = Image.new("RGB", (1040, 1090), "white")
draw = ImageDraw.Draw(canvas)

panels = [
    ("Original Satellite Image", original),
    ("Ground Truth", gt_color),
    ("Model Prediction", pred_color),
    ("GT / Prediction Overlay", overlay),
]

positions = [
    (5, 35), (523, 35),
    (5, 565), (523, 565)
]

for (title, image), (x, y) in zip(panels, positions):
    image = image.resize(panel_size, Image.Resampling.NEAREST)
    canvas.paste(image, (x, y))
    draw.text((x + 5, y - 22), title, fill="black")

output_path.parent.mkdir(parents=True, exist_ok=True)
canvas.save(output_path)

print("Comparison saved:", output_path)
print("Original size:", original.size)
print("GT classes:", np.unique(gt_raw))
print("Prediction classes:", np.unique(pred))
print("Class legend:")

for i, name in enumerate(names):
    print(i, name, palette[i].tolist())
