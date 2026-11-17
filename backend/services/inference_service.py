
from pathlib import Path
from copy import deepcopy
import re
from typing import Any, Dict, Optional, Sequence
from uuid import uuid4

import rasterio

from nlp.pipeline import SatQueryNLPPipeline
from integration.response_generator import ResponseGenerator


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "cv"
    / "outputs"
    / "predictions"
    / "backend_runs"
)


def _flood_input_error(image_file: Path) -> Optional[str]:
    """Return a user-safe validation message for unsupported flood inputs."""
    if image_file.suffix.lower() not in {".tif", ".tiff"}:
        return "Flood detection requires a two-band SAR GeoTIFF input."

    try:
        with rasterio.open(image_file) as source:
            if source.count != 2:
                return (
                    "Flood detection requires exactly 2 SAR bands; "
                    f"the selected raster has {source.count}."
                )
            if source.width < 224 or source.height < 224:
                return "Flood detection requires an image at least 224 × 224 pixels."
    except (rasterio.errors.RasterioError, OSError):
        return "Flood detection requires a readable two-band SAR GeoTIFF."

    return None


def _add_vegetation_pixel_summary(execution_result: Dict[str, Any]) -> None:
    """Derive vegetation image-pixel statistics from one real LoveDA result."""
    for item in execution_result.get("results", []):
        if item.get("task") != "LAND_COVER_DETECTION":
            continue
        result = item.get("result")
        if not isinstance(result, dict):
            continue
        counts = result.get("class_pixel_counts")
        width, height = result.get("image_width"), result.get("image_height")
        if (
            not isinstance(counts, dict)
            or type(width) is not int or width <= 0
            or type(height) is not int or height <= 0
            or any(type(value) is not int or value < 0 for value in counts.values())
            or "forest" not in counts or "agriculture" not in counts
        ):
            continue

        valid_pixels = sum(counts.values())
        image_pixels = width * height
        if valid_pixels != image_pixels:
            continue
        forest_pixels = counts["forest"]
        agriculture_pixels = counts["agriculture"]
        vegetation_pixels = forest_pixels + agriculture_pixels
        fraction = vegetation_pixels / valid_pixels
        result["vegetation_pixel_summary"] = {
            "forest_pixels": forest_pixels,
            "agriculture_pixels": agriculture_pixels,
            "total_vegetation_pixels": vegetation_pixels,
            "valid_image_pixels": valid_pixels,
            "vegetation_pixel_fraction": fraction,
            "vegetation_pixel_percentage": fraction * 100,
            "measurement": "image_pixels",
        }


def _building_spatial_distribution(result: Dict[str, Any]) -> Dict[str, Any]:
    """Count returned detection centers in a transparent 3x3 image grid."""
    width, height = result.get("image_width"), result.get("image_height")
    detections = result.get("detections")
    if (
        not isinstance(width, int) or width <= 0
        or not isinstance(height, int) or height <= 0
        or not isinstance(detections, list)
    ):
        return {"available": False, "reason": "Image dimensions or detection boxes are unavailable."}

    rows = ("upper", "middle", "lower")
    columns = ("left", "center", "right")
    counts = {f"{row}-{column}": 0 for row in rows for column in columns}
    valid_centers = 0
    for detection in detections:
        center = detection.get("center") if isinstance(detection, dict) else None
        if not isinstance(center, (list, tuple)) or len(center) != 2:
            box = detection.get("bbox_xyxy") if isinstance(detection, dict) else None
            if not isinstance(box, (list, tuple)) or len(box) != 4:
                continue
            center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        try:
            x, y = float(center[0]), float(center[1])
        except (TypeError, ValueError):
            continue
        if not (0 <= x <= width and 0 <= y <= height):
            continue
        col_index = min(int(x / width * 3), 2)
        row_index = min(int(y / height * 3), 2)
        counts[f"{rows[row_index]}-{columns[col_index]}"] += 1
        valid_centers += 1

    largest_label = max(counts, key=counts.get) if valid_centers else None
    return {
        "available": True,
        "method": "3x3 image-pixel grid over returned detection centers",
        "detection_count": valid_centers,
        "region_counts": counts,
        "largest_region": (
            {"label": largest_label, "count": counts[largest_label]}
            if largest_label else None
        ),
    }


def _is_building_distribution_followup(query: str) -> bool:
    return bool(
        re.search(r"\b(concentrat\w*|cluster\w*|distribution|spread|grouped)\b", query, re.I)
        and re.search(r"\b(they|them|those|these|buildings?)\b", query, re.I)
    )


def _is_previous_result_explanation(query: str) -> bool:
    asks_for_explanation = re.search(
        r"\b(explain|describe|summari[sz]e|summary|tell me more|what did you (?:find|detect|identify))\b",
        query,
        re.I,
    )
    refers_to_prior = re.search(
        r"\b(previous|prior|earlier|last|that|those|the result|the findings)\b",
        query,
        re.I,
    )
    return bool(asks_for_explanation and refers_to_prior)


def _task_family(task: str) -> Optional[str]:
    if task in {"BUILDING_COUNT", "BUILDING_DETECTION", "BUILDING_LOCATE"}:
        return "building"
    if task == "LAND_COVER_DETECTION":
        return "land_cover"
    if task == "BUILDING_CHANGE":
        return "change"
    if task in {"FLOODED_AREA_PRESENCE", "FLOODED_AREA_DETECTION"}:
        return "flood"
    return None


_REUSABLE_TASK_SOURCES = {
    # The three building tasks are views over the same detector output.
    "BUILDING_COUNT": {"BUILDING_COUNT", "BUILDING_DETECTION", "BUILDING_LOCATE"},
    "BUILDING_DETECTION": {"BUILDING_COUNT", "BUILDING_DETECTION", "BUILDING_LOCATE"},
    "BUILDING_LOCATE": {"BUILDING_COUNT", "BUILDING_DETECTION", "BUILDING_LOCATE"},
    "LAND_COVER_DETECTION": {"LAND_COVER_DETECTION"},
    "BUILDING_CHANGE": {"BUILDING_CHANGE"},
    "FLOODED_AREA_DETECTION": {"FLOODED_AREA_DETECTION", "FLOODED_AREA_PRESENCE"},
    "FLOODED_AREA_PRESENCE": {"FLOODED_AREA_DETECTION", "FLOODED_AREA_PRESENCE"},
}


def _result_supports_task(task_name: str, row: Dict[str, Any]) -> bool:
    """Check that one completed result contains the facts for this task view."""
    if not isinstance(row, dict) or row.get("execution_status") not in {"COMPLETED", "REUSED"}:
        return False
    result = row.get("result")
    source_task = row.get("task")
    compatible_sources = _REUSABLE_TASK_SOURCES.get(task_name)
    if not compatible_sources or source_task not in compatible_sources or not isinstance(result, dict):
        return False

    result_capability = result.get("capability")
    if result_capability is not None and result_capability not in compatible_sources:
        return False

    if task_name in {"BUILDING_COUNT", "BUILDING_DETECTION", "BUILDING_LOCATE"}:
        return type(result.get("building_count")) is int and isinstance(result.get("detections"), list)
    if task_name == "LAND_COVER_DETECTION":
        return isinstance(result.get("class_pixel_counts"), dict)
    if task_name == "BUILDING_CHANGE":
        return (
            type(result.get("changed_pixels_at_model_resolution")) is int
            and type(result.get("total_pixels_at_model_resolution")) is int
        )
    if task_name == "FLOODED_AREA_DETECTION":
        return type(result.get("flood_pixels")) is int and type(result.get("valid_pixels")) is int
    if task_name == "FLOODED_AREA_PRESENCE":
        return (
            isinstance(result.get("flood_present"), bool)
            or (type(result.get("flood_pixels")) is int and type(result.get("valid_pixels")) is int)
        )
    return False


def _requested_previous_families(query: str):
    """Return explicit capability families mentioned in a prior-result query."""
    text = query.lower()
    families = set()
    if re.search(r"\b(buildings?|structures?)\b", text):
        families.add("building")
    if re.search(r"\b(land[ -]?cover|vegetation|forest|agricultur\w*)\b", text):
        families.add("land_cover")
    if re.search(r"\b(changes?|before[ -]and[ -]after|comparison)\b", text):
        families.add("change")
    if re.search(r"\b(flood(?:ing|ed)?|sar)\b", text):
        families.add("flood")
    return families


def _reusable_results(tasks, previous_analysis):
    if not isinstance(previous_analysis, dict) or previous_analysis.get("status") != "success":
        return None
    previous_rows = previous_analysis.get("execution", {}).get("results", [])
    if not isinstance(previous_rows, list):
        return None
    completed = [row for row in previous_rows if isinstance(row, dict)]
    reused = []
    consumed = set()
    for task in tasks:
        if not isinstance(task, dict):
            return None
        task_name = task.get("task")
        match_index = next((
            index for index, row in enumerate(completed)
            if index not in consumed and _result_supports_task(task_name, row)
        ), None)
        if match_index is None:
            return None
        consumed.add(match_index)
        match = completed[match_index]
        result = deepcopy(match["result"])
        source_capability = result.get("capability") or match.get("task")
        if source_capability != task_name:
            result["source_capability"] = source_capability
        result["capability"] = task_name
        reused.append({
            "task": task_name,
            "execution_status": "COMPLETED",
            "reused": True,
            "result": result,
        })
    return reused if reused else None


class SatQueryInferenceService:
    """
    Coordinates the existing NLP pipeline and verified CV executors.

    Flow:
        Natural Language Query
            -> M1 + M2
            -> Task Planner
            -> Query Router
            -> Capability Validation
            -> Actual CV Execution
            -> Structured Results
    """

    def __init__(
        self,
        pipeline: Optional[SatQueryNLPPipeline] = None,
        output_dir: Optional[str] = None,
        response_generator: Optional[ResponseGenerator] = None,
    ):
        self.pipeline = pipeline
        self.response_generator = response_generator or ResponseGenerator()

        self.output_dir = (
            Path(output_dir)
            if output_dir
            else DEFAULT_OUTPUT_DIR
        )

    def _get_pipeline(self) -> SatQueryNLPPipeline:
        """
        Initialize the NLP pipeline only when first required.
        Reuse the same pipeline and registered CV executors.
        """

        if self.pipeline is None:
            self.pipeline = SatQueryNLPPipeline()

        return self.pipeline

    def run_analysis(
        self,
        query: str,
        image_path: str,
        conversation: Optional[Sequence[str]] = None,
        second_image_path: Optional[str] = None,
        previous_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a natural-language query and execute
        all verified CV tasks against the supplied image.
        """

        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string.")

        if not isinstance(image_path, str) or not image_path.strip():
            raise ValueError("Image path is required.")

        image_file = Path(image_path)

        if not image_file.is_file():
            raise FileNotFoundError(
                f"Uploaded image not found: {image_file}"
            )

        second_image_file = None
        if second_image_path is not None:
            second_image_file = Path(second_image_path)
            if not second_image_file.is_file():
                raise FileNotFoundError(
                    f"Second uploaded image not found: {second_image_file}"
                )

        # Generate a unique ID to prevent output overwriting.
        run_id = str(uuid4())

        task_output_dir = self.output_dir / run_id

        # Stage 1: Complete NLP processing and capability validation.
        pipeline = self._get_pipeline()

        nlp_result = pipeline.process_query(
            query=query,
            conversation=conversation,
        )

        context_resolution = None
        previous_rows = (
            previous_analysis.get("execution", {}).get("results", [])
            if isinstance(previous_analysis, dict) else []
        )
        previous_building = next((
            row.get("result") for row in previous_rows
            if _result_supports_task("BUILDING_DETECTION", row)
        ), None)

        if _is_previous_result_explanation(query):
            requested_families = _requested_previous_families(query)
            previous_available = [
                row for row in previous_rows
                if isinstance(row, dict)
                and _task_family(row.get("task", "")) is not None
                and (not requested_families or _task_family(row.get("task", "")) in requested_families)
                and _result_supports_task(row.get("task"), row)
            ]
            if previous_available:
                reused_rows = []
                for row in previous_available:
                    reused_rows.append({
                        "task": row["task"],
                        "execution_status": "COMPLETED",
                        "reused": True,
                        "result": deepcopy(row["result"]),
                    })
                execution_result = {
                    "execution_started": False,
                    "execution_status": "COMPLETED",
                    "total_tasks": len(reused_rows),
                    "completed_tasks": len(reused_rows),
                    "failed_tasks": 0,
                    "reused_previous_result": True,
                    "results": reused_rows,
                }
                context_resolution = {
                    "status": "ANSWERED_FROM_PREVIOUS_RESULT",
                    "capabilities": [row["task"] for row in reused_rows],
                    "source_run_id": previous_analysis.get("run_id"),
                }
                nlp_result["context_resolution"] = context_resolution
                response = {
                    "status": "success",
                    "run_id": run_id,
                    "query": query,
                    "nlp": nlp_result,
                    "execution": execution_result,
                }
                return self._add_response(response, conversation, context_resolution, pipeline)

            context_resolution = {
                "status": "CAPABILITY_UNAVAILABLE" if requested_families else "CONTEXT_UNAVAILABLE",
                "requested_capabilities": sorted(requested_families),
            }
            nlp_result["context_resolution"] = context_resolution
            reason = (
                "There is no completed previous result for the requested capability in this image session."
                if requested_families
                else "There is no earlier completed analysis in this image session to explain yet."
            )
            response = {
                "status": "blocked",
                "run_id": run_id,
                "query": query,
                "nlp": nlp_result,
                "execution": {
                    "execution_started": False,
                    "execution_status": "BLOCKED",
                    "validation": {
                        "overall_status": "BLOCKED",
                        "reason": reason,
                    },
                    "results": [],
                },
            }
            return self._add_response(response, conversation, context_resolution, pipeline)

        if previous_building and _is_building_distribution_followup(query):
            distribution = _building_spatial_distribution(previous_building)
            result = deepcopy(previous_building)
            result["spatial_distribution"] = distribution
            execution_result = {
                "execution_started": False,
                "execution_status": "COMPLETED",
                "total_tasks": 1,
                "completed_tasks": 1,
                "failed_tasks": 0,
                "reused_previous_result": True,
                "results": [{
                    "task": "BUILDING_DETECTION",
                    "execution_status": "COMPLETED",
                    "reused": True,
                    "result": result,
                }],
            }
            context_resolution = {
                "status": "ANSWERED_FROM_PREVIOUS_RESULT",
                "source_capability": "BUILDING_DETECTION",
                "method": distribution.get("method"),
                "spatial_distribution": distribution,
            }
            nlp_result["context_resolution"] = context_resolution
            response = {
                "status": "success",
                "run_id": run_id,
                "query": query,
                "nlp": nlp_result,
                "execution": execution_result,
            }
            return self._add_response(response, conversation, context_resolution, pipeline)

        # Reuse a previous real model result when the current task asks for
        # information that result already contains. This runs M1/M2/planning
        # for the follow-up but avoids repeating CV inference.
        reused = _reusable_results(
            nlp_result.get("routing", {}).get("tasks", []),
            previous_analysis,
        )
        if reused:
            execution_result = {
                "execution_started": False,
                "execution_status": "COMPLETED",
                "total_tasks": len(reused),
                "completed_tasks": len(reused),
                "failed_tasks": 0,
                "reused_previous_result": True,
                "results": reused,
            }
            context_resolution = {
                "status": "REUSED_PREVIOUS_CV_RESULT",
                "capabilities": [row["task"] for row in reused],
                "source_run_id": previous_analysis.get("run_id"),
            }
            nlp_result["context_resolution"] = context_resolution
            response = {
                "status": "success",
                "run_id": run_id,
                "query": query,
                "nlp": nlp_result,
                "execution": execution_result,
            }
            return self._add_response(response, conversation, context_resolution, pipeline)

        validation = nlp_result["capability_validation"]

        # Stage 2: Block execution if any task is unavailable.
        if validation["overall_status"] != "READY":
            response = {
                "status": "blocked",
                "run_id": run_id,
                "query": query,
                "nlp": nlp_result,
                "execution": {
                    "execution_started": False,
                    "execution_status": "BLOCKED",
                    "validation": validation,
                    "results": [],
                },
            }
            return self._add_response(response, conversation, context_resolution, pipeline)

        flood_tasks = {
            "FLOODED_AREA_DETECTION",
            "FLOODED_AREA_PRESENCE",
        }
        if any(
            task.get("task") in flood_tasks
            for task in nlp_result["routing"]["tasks"]
        ):
            input_error = _flood_input_error(image_file)
            if input_error:
                response = {
                    "status": "blocked",
                    "run_id": run_id,
                    "query": query,
                    "nlp": nlp_result,
                    "execution": {
                        "execution_started": False,
                        "execution_status": "BLOCKED",
                        "validation": {
                            "overall_status": "BLOCKED",
                            "reason": input_error,
                        },
                        "results": [],
                    },
                }
                return self._add_response(response, conversation, context_resolution, pipeline)

        # Stage 3: Execute actual registered CV capabilities.
        execution_result = pipeline.registry.execute_tasks(
            tasks=nlp_result["routing"]["tasks"],
            image_path=str(image_file),
            output_dir=str(task_output_dir),
            second_image_path=(
                str(second_image_file) if second_image_file else None
            ),
        )

        if execution_result.get("execution_status") == "COMPLETED":
            _add_vegetation_pixel_summary(execution_result)

        execution_status = execution_result["execution_status"]

        final_status = {
            "COMPLETED": "success",
            "BLOCKED": "blocked",
        }.get(execution_status, "failed")

        response = {
            "status": final_status,
            "run_id": run_id,
            "query": query,
            "nlp": nlp_result,
            "execution": execution_result,
        }
        return self._add_response(response, conversation, context_resolution, pipeline)

    def _add_response(self, response, conversation, context_resolution, pipeline):
        generated = self.response_generator.generate(
            query=response.get("query", ""),
            status=response.get("status", "failed"),
            execution=response.get("execution"),
            nlp=response.get("nlp"),
            conversation=conversation,
            context_resolution=context_resolution,
        )
        response["assistant_response"] = generated["answer"]
        response["response_generation"] = {
            "status": generated["status"],
            "model": generated["model"],
        }
        nlp = response.get("nlp") or {}
        response["nlp_insights"] = {
            "original_query": nlp.get("original_query"),
            "m1": nlp.get("m1"),
            "m2": {
                **(nlp.get("m2") or {}),
                "model": getattr(getattr(pipeline, "m2", None), "model", None),
            },
            "subquery_m1_results": nlp.get("subquery_m1_results", []),
            "task_plan": nlp.get("task_plan"),
            "routing": nlp.get("routing"),
            "capability_validation": nlp.get("capability_validation"),
            "context_resolution": context_resolution,
            "response_generation": response["response_generation"],
        }
        return response
