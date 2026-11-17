import argparse
from pathlib import Path

import yaml
from ultralytics import YOLO


CONFIG_PATH = Path("cv/configs/building.yaml")


def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(CONFIG_PATH)

    with CONFIG_PATH.open("r", encoding="utf-8-sig") as f:
        config = yaml.safe_load(f)

    required = ["model", "data", "epochs", "imgsz", "batch", "device"]

    for key in required:
        if key not in config:
            raise ValueError(f"Missing config parameter: {key}")

    if not Path(config["model"]).exists():
        raise FileNotFoundError(f"Model weights not found: {config['model']}")

    if not Path(config["data"]).exists():
        raise FileNotFoundError(f"Dataset YAML not found: {config['data']}")

    return config


def main():
    parser = argparse.ArgumentParser(
        description="SpaceNet2 building detection YOLO training"
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="Explicitly start model training"
    )
    args = parser.parse_args()

    config = load_config()

    print("SPACE NET2 BUILDING DETECTOR")
    print("\nTraining configuration:")

    for key, value in config.items():
        print(f"{key}: {value}")

    if not args.start:
        print("\nConfiguration verified.")
        print("Training NOT started.")
        print("Use --start when ready to begin training.")
        return

    print("\nInitializing YOLO model...")
    model = YOLO(config["model"])

    training_args = {
        key: value
        for key, value in config.items()
        if key != "model"
    }

    print("\nStarting training...")
    model.train(**training_args)


if __name__ == "__main__":
    main()
