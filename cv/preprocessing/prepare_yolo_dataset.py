import csv
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SPLIT_DIR = ROOT / "data/processed/cv/spacenet2_yolo/splits"
OUTPUT = ROOT / "data/processed/cv/spacenet2_yolo"

EXPECTED = {
    "train": 679,
    "val": 159,
    "test": 140,
}


def link_or_copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists():
        if os.path.samefile(source, destination):
            return "existing_link"

        if source.stat().st_size == destination.stat().st_size:
            import filecmp
            if filecmp.cmp(source, destination, shallow=False):
                return "existing_copy"

        raise RuntimeError(f"Destination conflict: {destination}")

    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def main():
    stats = {
        name: {"images": 0, "labels": 0}
        for name in EXPECTED
    }

    methods = {
        "hardlink": 0,
        "copy": 0,
        "existing_link": 0,
        "existing_copy": 0,
    }

    for split, expected_count in EXPECTED.items():
        manifest = SPLIT_DIR / f"{split}.csv"

        if not manifest.is_file():
            raise FileNotFoundError(manifest)

        with manifest.open(
            encoding="utf-8", newline=""
        ) as file:
            entries = list(csv.DictReader(file))

        if len(entries) != expected_count:
            raise RuntimeError(
                f"{split}: expected {expected_count}, got {len(entries)}"
            )

        for entry in entries:
            source_image = ROOT / entry["image"]
            source_label = ROOT / entry["label"]

            if not source_image.is_file():
                raise FileNotFoundError(source_image)

            if not source_label.is_file():
                raise FileNotFoundError(source_label)

            image_destination = (
                OUTPUT / "images" / split / source_image.name
            )
            label_destination = (
                OUTPUT / "labels" / split /
                f"{source_image.stem}.txt"
            )

            image_method = link_or_copy(
                source_image, image_destination
            )
            label_method = link_or_copy(
                source_label, label_destination
            )

            methods[image_method] += 1
            methods[label_method] += 1

            stats[split]["images"] += 1
            stats[split]["labels"] += 1

    yaml_content = (
        f"path: {OUTPUT.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n\n"
        "names:\n"
        "  0: building\n"
    )

    (OUTPUT / "dataset.yaml").write_text(
        yaml_content,
        encoding="utf-8",
    )

    print("\nYOLO DATASET PREPARATION")
    for split, values in stats.items():
        print(f"\n{split.upper()}")
        print("Images:", values["images"])
        print("Labels:", values["labels"])

    print("\nLINK/COPY METHODS")
    for method, count in methods.items():
        print(f"{method}: {count}")

    print("\nDataset YAML:", OUTPUT / "dataset.yaml")
    print("Preparation completed.")


if __name__ == "__main__":
    main()
