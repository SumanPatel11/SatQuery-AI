
from pathlib import Path
from typing import Any, Callable, Dict, List


class CapabilityRegistry:
    """
    Central registry for verified CV execution capabilities.

    A capability is executable only after:
    1. Its implementation file is verified.
    2. Its required model artifacts are verified.
    3. A callable inference executor is registered.
    """

    KNOWN_CAPABILITIES = [
        "BUILDING_COUNT",
        "BUILDING_DETECTION",
        "BUILDING_LOCATE",
        "ROAD_COUNT",
        "ROAD_DETECTION",
        "ROAD_LOCATE",
        "WATER_PRESENCE",
        "WATER_DETECTION",
        "WATER_LOCATE",
        "VEGETATION_AREA",
        "LAND_COVER_AREA",
        "LAND_COVER_DETECTION",
        "BUILDING_CHANGE",
        "FLOODED_AREA_PRESENCE",
        "FLOODED_AREA_DETECTION",
    ]

    def __init__(self):
        self._capabilities = {
            name: {
                "name": name,
                "status": "NOT_VERIFIED",
                "executor": None,
                "implementation": None,
                "artifacts": [],
                "reason": (
                    "Implementation and pretrained weights not verified."
                ),
            }
            for name in self.KNOWN_CAPABILITIES
        }

    @staticmethod
    def _verify_file(path: str) -> bool:
        file_path = Path(path)

        return (
            file_path.is_file()
            and file_path.stat().st_size > 0
        )

    def register(
        self,
        name: str,
        executor: Callable,
        implementation_path: str,
        artifact_paths: List[str],
    ) -> Dict[str, Any]:

        if name not in self._capabilities:
            raise ValueError(f"Unknown CV capability: {name}")

        if not callable(executor):
            raise TypeError("Executor must be callable.")

        if not implementation_path:
            raise ValueError("Implementation path is required.")

        if not self._verify_file(implementation_path):
            raise FileNotFoundError(
                "CV implementation file is missing or empty."
            )

        if not isinstance(artifact_paths, list) or not artifact_paths:
            raise ValueError(
                "At least one model artifact path is required."
            )

        missing_artifacts = [
            path for path in artifact_paths
            if not self._verify_file(path)
        ]

        if missing_artifacts:
            raise FileNotFoundError(
                "Missing or empty model artifacts: "
                + ", ".join(missing_artifacts)
            )

        self._capabilities[name] = {
            "name": name,
            "status": "AVAILABLE",
            "executor": executor,
            "implementation": str(Path(implementation_path)),
            "artifacts": [
                str(Path(path)) for path in artifact_paths
            ],
            "reason": None,
        }

        return self.get(name)

    def get(self, name: str) -> Dict[str, Any]:
        capability = self._capabilities.get(name)

        if capability is None:
            return {
                "name": name,
                "status": "UNKNOWN",
                "reason": "Capability is not registered.",
            }

        # Never expose the executor callable publicly.
        return {
            key: value
            for key, value in capability.items()
            if key != "executor"
        }

    def list_capabilities(self) -> List[Dict[str, Any]]:
        return [
            self.get(name)
            for name in self._capabilities
        ]

    def validate_tasks(
        self,
        tasks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        if not isinstance(tasks, list):
            raise TypeError("Tasks must be supplied as a list.")

        validated = []

        for task in tasks:
            if not isinstance(task, dict):
                raise ValueError("Invalid task entry.")

            task_name = task.get("task")

            if not isinstance(task_name, str) or not task_name:
                raise ValueError("Task name is missing.")

            capability = self.get(task_name)
            available = capability["status"] == "AVAILABLE"

            validated.append({
                "task": task_name,
                "source_subquery": task.get("source_subquery"),
                "operation": task.get("operation"),
                "target": task.get("target"),
                "capability_status": capability["status"],
                "execution_status": (
                    "READY" if available else "BLOCKED"
                ),
                "reason": capability.get("reason"),
            })

        ready_count = sum(
            item["execution_status"] == "READY"
            for item in validated
        )

        return {
            "tasks": validated,
            "total_tasks": len(validated),
            "ready_tasks": ready_count,
            "blocked_tasks": len(validated) - ready_count,
            "overall_status": (
                "READY"
                if ready_count == len(validated) and len(validated) > 0
                else "BLOCKED"
            ),
            "execution_started": False,
        }

    def execute_tasks(
        self,
        tasks: List[Dict[str, Any]],
        image_path: str,
        output_dir: str,
    ) -> Dict[str, Any]:
        """
        Execute verified CV capabilities against an uploaded image.

        All tasks are validated before execution begins.
        Each task receives its own output directory.
        """

        if not isinstance(tasks, list) or not tasks:
            raise ValueError("At least one task is required.")

        if not isinstance(image_path, str) or not image_path.strip():
            raise ValueError("Image path is required.")

        if not isinstance(output_dir, str) or not output_dir.strip():
            raise ValueError("Output directory is required.")

        image_file = Path(image_path)

        if not image_file.is_file():
            raise FileNotFoundError(
                f"Input image not found: {image_file}"
            )

        # Validate every task before starting any inference.
        validation = self.validate_tasks(tasks)

        if validation["overall_status"] != "READY":
            return {
                "execution_started": False,
                "execution_status": "BLOCKED",
                "validation": validation,
                "results": [],
            }

        results = []
        output_root = Path(output_dir)

        for index, task in enumerate(tasks, start=1):
            task_name = task["task"]

            # Retrieve the actual registered executor.
            capability = self._capabilities[task_name]
            executor = capability["executor"]

            if not callable(executor):
                raise RuntimeError(
                    f"Executor unavailable: {task_name}"
                )

            task_output_dir = (
                output_root / f"{index}_{task_name.lower()}"
            )

            task_output_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            # Execute the genuine registered CV inference function.
            try:
                result = executor(
                    image_path=str(image_file),
                    output_dir=str(task_output_dir),
                    save_outputs=True,
                )

                if not isinstance(result, dict):
                    raise RuntimeError(
                        f"Invalid executor result: {task_name}"
                    )

                results.append({
                    "task": task_name,
                    "execution_status": "COMPLETED",
                    "result": result,
                })

            except Exception as exc:
                results.append({
                    "task": task_name,
                    "execution_status": "FAILED",
                    "error": str(exc),
                })

                # Stop after a failure; do not claim overall success.
                return {
                    "execution_started": True,
                    "execution_status": "FAILED",
                    "total_tasks": len(tasks),
                    "completed_tasks": sum(
                        item["execution_status"] == "COMPLETED"
                        for item in results
                    ),
                    "failed_tasks": 1,
                    "results": results,
                }

        return {
            "execution_started": True,
            "execution_status": "COMPLETED",
            "total_tasks": len(tasks),
            "completed_tasks": len(results),
            "failed_tasks": 0,
            "results": results,
        }
