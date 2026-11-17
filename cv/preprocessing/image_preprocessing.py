import csv
import json
import numpy as np
import rasterio
from pathlib import Path
from PIL import Image

BASE = Path("data/processed/cv/spacenet2_yolo")
OUTPUT = Path("data/processed/cv/spacenet2_rgb_yolo")

LIMITS_LOW = [127.0, 225.0, 224.0]
LIMITS_HIGH = [486.0, 504.0, 380.0]
SPLITS = ["train", "val", "test"]


def convert_image(source, destination):
    with rasterio.open(source) as src:
        if src.count != 3 or (src.width, src.height) != (650, 650):
            raise ValueError(f"Unexpected TIFF dimensions/bands: {source}")

        data = src.read([1, 2, 3]).astype(np.float32)

    rgb = np.empty(data.shape, dtype=np.uint8)

    for band in range(3):
        scaled = (
            (data[band] - LIMITS_LOW[band])
            * 255.0
            / (LIMITS_HIGH[band] - LIMITS_LOW[band])
        )
        rgb[band] = np.clip(scaled, 0, 255).astype(np.uint8)

    image = np.moveaxis(rgb, 0, -1)
    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image, mode="RGB").save(destination, format="PNG")

    with Image.open(destination) as check:
        if check.mode != "RGB" or check.size != (650, 650):
            raise ValueError(f"PNG validation failed: {destination}")

    return int(image.min()), int(image.max())


def main():
    report = {
        "normalization": {
            "method": "training non-zero pixel P2 to P98",
            "low": LIMITS_LOW,
            "high": LIMITS_HIGH
        },
        "splits": {},
        "total_images": 0
    }

    for split in SPLITS:
        manifest = BASE / "splits" / f"{split}.csv"

        with manifest.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        if not rows:
            raise ValueError(f"Empty manifest: {manifest}")

        split_results = []

        for index, row in enumerate(rows, start=1):
            source = Path(row["image"])
            destination = OUTPUT / "images" / split / f"{source.stem}.png"

            minimum, maximum = convert_image(source, destination)

            split_results.append({
                "image": source.name,
                "output": str(destination),
                "minimum": minimum,
                "maximum": maximum
            })

            if index % 100 == 0 or index == len(rows):
                print(f"{split}: {index}/{len(rows)}")

        report["splits"][split] = {
            "count": len(split_results),
            "images": split_results
        }
        report["total_images"] += len(split_results)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT / "preprocessing_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\nPREPROCESSING COMPLETE")
    print("Total images:", report["total_images"])
    print("Output:", OUTPUT)
    print("Report:", report_path)


if __name__ == "__main__":
    main()
