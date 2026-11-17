from pathlib import Path

from nlp.capability_registry import CapabilityRegistry
from cv.models.flood import detect_flood, detect_flood_presence
from cv.models.building import detect_buildings, count_buildings, locate_buildings
from cv.models.change_v2 import _executor as change_v2_executor
from cv.models.land_cover import detect_land_cover


ROOT = Path(__file__).resolve().parents[1]

IMPLEMENTATION = ROOT / "cv" / "models" / "flood.py"

MODEL_DIR = ROOT / "models" / "cv" / "radiance_sen1floods11_v2"

MODEL_DEFINITION = MODEL_DIR / "model.py"
CHECKPOINT = MODEL_DIR / "best.pt"


def create_capability_registry() -> CapabilityRegistry:
    """
    Create the central CV registry and register only verified
    capabilities with their actual inference executors.
    """

    registry = CapabilityRegistry()

    artifacts = [
        str(MODEL_DEFINITION),
        str(CHECKPOINT),
    ]

    registry.register(
        name="FLOODED_AREA_DETECTION",
        executor=detect_flood,
        implementation_path=str(IMPLEMENTATION),
        artifact_paths=artifacts,
    )

    registry.register(
        name="FLOODED_AREA_PRESENCE",
        executor=detect_flood_presence,
        implementation_path=str(IMPLEMENTATION),
        artifact_paths=artifacts,
    )

    building_implementation = ROOT / "cv" / "models" / "building.py"
    building_checkpoint = (
        ROOT / "runs" / "detect" / "runs" / "detect"
        / "spacenet2_building_yolo26n" / "weights" / "best.pt"
    )

    for name, executor in [
        ("BUILDING_DETECTION", detect_buildings),
        ("BUILDING_COUNT", count_buildings),
        ("BUILDING_LOCATE", locate_buildings),
    ]:
        registry.register(
            name=name,
            executor=executor,
            implementation_path=str(building_implementation),
            artifact_paths=[str(building_checkpoint)],
        )

    change_implementation = ROOT / "cv" / "models" / "change_v2.py"
    change_checkpoint = ROOT / "models" / "cv" / "levir_cd_change_v2" / "best.pt"

    def detect_building_change(image_path, second_image_path=None, **kwargs):
        return change_v2_executor.predict(
            image_path=image_path,
            second_image_path=second_image_path,
            **kwargs,
        )

    registry.register(
        name="BUILDING_CHANGE",
        executor=detect_building_change,
        implementation_path=str(change_implementation),
        artifact_paths=[str(change_checkpoint)],
    )

    land_cover_implementation = ROOT / "cv" / "models" / "land_cover.py"
    land_cover_checkpoint = ROOT / "models" / "cv" / "loveda_land_cover" / "best.pt"
    registry.register(
        name="LAND_COVER_DETECTION",
        executor=detect_land_cover,
        implementation_path=str(land_cover_implementation),
        artifact_paths=[str(land_cover_checkpoint)],
    )

    return registry
