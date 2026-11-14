from pathlib import Path

from nlp.capability_registry import CapabilityRegistry
from cv.models.flood import detect_flood, detect_flood_presence


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

    return registry
