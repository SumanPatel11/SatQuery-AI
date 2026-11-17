from pathlib import Path
import tempfile
import unittest

from cv.registry import create_capability_registry
from cv.models.land_cover import detect_land_cover
from nlp.query_router import HybridQueryRouter


class LandCoverRegistryTests(unittest.TestCase):
    def test_registers_only_segmentation_capability(self):
        registry = create_capability_registry()
        self.assertEqual(registry.get("LAND_COVER_DETECTION")["status"], "AVAILABLE")
        self.assertNotEqual(registry.get("LAND_COVER_AREA_UNSUPPORTED")["status"], "AVAILABLE")

    def test_area_routes_to_unavailable_capability(self):
        result = HybridQueryRouter().route(
            m1_result={"intent": "LAND_COVER_ANALYSIS"},
            m2_result={"subqueries": ["Calculate land-cover area"], "combine": "SINGLE"},
            subquery_m1_results=[{"intent": "LAND_COVER_ANALYSIS"}],
            task_plan={"tasks": [{
                "source_subquery": "Calculate land-cover area",
                "operation": "AREA",
                "target": "land_cover",
                "region": "none",
                "spatial_relation": "none",
            }]},
        )
        self.assertEqual(result["tasks"][0]["task"], "LAND_COVER_AREA_UNSUPPORTED")
        self.assertEqual(result["tasks"][0]["status"], "NEEDS_REVIEW")
        self.assertEqual(create_capability_registry().validate_tasks(result["tasks"])["overall_status"], "BLOCKED")

    def test_unknown_target_is_blocked_without_registry_exception(self):
        result = HybridQueryRouter().route(
            m1_result={"intent": "OUT_OF_SCOPE"},
            m2_result={"subqueries": ["Analyze something unclear"], "combine": "SINGLE"},
            subquery_m1_results=[{"intent": "OUT_OF_SCOPE"}],
            task_plan={"tasks": [{
                "source_subquery": "Analyze something unclear",
                "operation": "DETECT",
                "target": "unknown",
                "region": "none",
                "spatial_relation": "none",
            }]},
        )

        self.assertEqual(result["tasks"][0]["status"], "NEEDS_REVIEW")
        self.assertEqual(result["tasks"][0]["task"], "UNSUPPORTED_TASK")
        validation = create_capability_registry().validate_tasks(result["tasks"])
        self.assertEqual(validation["overall_status"], "BLOCKED")
        self.assertEqual(validation["tasks"][0]["capability_status"], "UNKNOWN")

    def test_segmentation_and_pixel_counts_share_registered_loveda_executor(self):
        subqueries = [
            "Segment the land-cover classes in the image.",
            "Count the number of pixels in each land-cover class.",
        ]
        result = HybridQueryRouter().route(
            m1_result={"intent": "OUT_OF_SCOPE"},
            m2_result={"subqueries": subqueries, "combine": "AND"},
            subquery_m1_results=[
                {"intent": "LAND_COVER_ANALYSIS"},
                {"intent": "LAND_COVER_ANALYSIS"},
            ],
            task_plan={"tasks": [
                {
                    "source_subquery": subqueries[0],
                    "operation": "DETECT",
                    "target": "land_cover",
                    "region": "none",
                    "spatial_relation": "none",
                },
                {
                    "source_subquery": subqueries[1],
                    "operation": "COUNT",
                    "target": "land_cover",
                    "region": "none",
                    "spatial_relation": "none",
                },
            ]},
        )

        self.assertEqual(len(result["tasks"]), 1)
        self.assertEqual(result["tasks"][0]["task"], "LAND_COVER_DETECTION")
        self.assertEqual(result["tasks"][0]["operation"], "DETECT")
        self.assertEqual(
            result["tasks"][0]["requested_operations"],
            ["DETECT", "COUNT"],
        )
        validation = create_capability_registry().validate_tasks(result["tasks"])
        self.assertEqual(validation["overall_status"], "READY")

    def test_building_change_without_after_image_is_blocked(self):
        registry = create_capability_registry()
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "before.png"
            image.write_bytes(b"placeholder")
            result = registry.execute_tasks(
                tasks=[{"task": "BUILDING_CHANGE"}],
                image_path=str(image),
                output_dir=str(Path(directory) / "outputs"),
            )
        self.assertEqual(result["execution_status"], "BLOCKED")
        self.assertIn("before image and an after image", result["validation"]["reason"])

    @unittest.skipUnless(
        Path("models/cv/loveda_land_cover/best.pt").is_file()
        and Path("spacenet_rgb_preview.png").is_file(),
        "Local LoveDA checkpoint or fixture image is unavailable",
    )
    def test_executor_output_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            result = detect_land_cover(
                "spacenet_rgb_preview.png",
                output_dir=directory,
                save_outputs=True,
            )
            self.assertEqual(result["capability"], "LAND_COVER_DETECTION")
            self.assertEqual(sum(result["class_pixel_counts"].values()), result["image_width"] * result["image_height"])
            self.assertTrue(Path(result["outputs"]["segmentation_mask"]).is_file())
            self.assertNotIn("area", result)


if __name__ == "__main__":
    unittest.main()
