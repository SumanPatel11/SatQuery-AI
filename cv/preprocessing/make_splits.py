import csv
import json
from pathlib import Path

import rasterio

ROOT = Path(__file__).resolve().parents[2]

IMAGE_DIR = ROOT / "data/raw/cv/building/spacenet2/AOI_3_Paris_Train/RGB-PanSharpen"
LABEL_DIR = ROOT / "data/processed/cv/spacenet2_yolo/labels"
OUTPUT_DIR = ROOT / "data/processed/cv/spacenet2_yolo/splits"

EXPECTED = {
    "train": 679,
    "val": 159,
    "test": 140,
    "excluded": 170,
}


def main():
    images = sorted(IMAGE_DIR.glob("*.tif"))

    if len(images) != 1148:
        raise RuntimeError(f"Expected 1148 images, found {len(images)}")

    tiles = []

    for image in images:
        label = LABEL_DIR / f"{image.stem}.txt"

        if not label.is_file():
            raise FileNotFoundError(label)

        with rasterio.open(image) as src:
            b = src.bounds
            lon = round((b.left + b.right) / 2, 9)
            lat = round((b.bottom + b.top) / 2, 9)

        tiles.append({
            "image": image,
            "label": label,
            "lon": lon,
            "lat": lat,
            "boxes": len(label.read_text(encoding="utf-8").splitlines()),
        })

    longitudes = sorted({item["lon"] for item in tiles})
    col_index = {lon: i for i, lon in enumerate(longitudes)}

    assignments = {
        "train": [],
        "val": [],
        "test": [],
        "excluded": [],
    }

    for item in tiles:
        col = col_index[item["lon"]]

        if col <= 46:
            split = "train"
        elif 50 <= col <= 55:
            split = "val"
        elif col >= 59:
            split = "test"
        else:
            split = "excluded"

        item["column"] = col
        item["split"] = split
        assignments[split].append(item)

    # Confirm expected counts from the completed feasibility audit.
    for name, expected_count in EXPECTED.items():
        actual = len(assignments[name])
        if actual != expected_count:
            raise RuntimeError(
                f"{name}: expected {expected_count}, found {actual}"
            )

    # Confirm spatial columns do not overlap.
    column_sets = {
        name: {item["column"] for item in items}
        for name, items in assignments.items()
    }

    for first, second in (
        ("train", "val"),
        ("val", "test"),
        ("train", "test"),
    ):
        if column_sets[first] & column_sets[second]:
            raise RuntimeError(f"Spatial leakage: {first} / {second}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    report = {
        "method": "vertical geographic spatial split",
        "boundaries": {
            "train": "columns 0-46",
            "validation": "columns 50-55",
            "test": "columns 59-64",
            "buffer": ["47-49", "56-58"],
        },
        "spatial_leakage_check": "PASSED",
        "splits": {},
        "total_images": len(tiles),
    }

    for name, items in assignments.items():
        manifest = OUTPUT_DIR / f"{name}.csv"

        with manifest.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "image",
                    "label",
                    "column",
                    "longitude",
                    "latitude",
                    "building_count",
                ],
            )
            writer.writeheader()

            for item in items:
                writer.writerow({
                    "image": item["image"].relative_to(ROOT).as_posix(),
                    "label": item["label"].relative_to(ROOT).as_posix(),
                    "column": item["column"],
                    "longitude": item["lon"],
                    "latitude": item["lat"],
                    "building_count": item["boxes"],
                })

        report["splits"][name] = {
            "images": len(items),
            "positive_images": sum(x["boxes"] > 0 for x in items),
            "negative_images": sum(x["boxes"] == 0 for x in items),
            "building_boxes": sum(x["boxes"] for x in items),
            "columns": sorted({x["column"] for x in items}),
        }

    (OUTPUT_DIR / "split_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("\nFINAL VERTICAL SPATIAL SPLIT")

    for name, values in report["splits"].items():
        print(f"\n{name.upper()}")
        for key, value in values.items():
            print(f"{key}: {value}")

    print("\nTotal images:", len(tiles))
    print("Spatial leakage check: PASSED")
    print("Output:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
