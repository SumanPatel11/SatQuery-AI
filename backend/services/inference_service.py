
from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from uuid import uuid4

from nlp.pipeline import SatQueryNLPPipeline


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "cv"
    / "outputs"
    / "predictions"
    / "backend_runs"
)


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
    ):
        self.pipeline = pipeline

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

        # Generate a unique ID to prevent output overwriting.
        run_id = str(uuid4())

        task_output_dir = self.output_dir / run_id

        # Stage 1: Complete NLP processing and capability validation.
        pipeline = self._get_pipeline()

        nlp_result = pipeline.process_query(
            query=query,
            conversation=conversation,
        )

        validation = nlp_result["capability_validation"]

        # Stage 2: Block execution if any task is unavailable.
        if validation["overall_status"] != "READY":
            return {
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

        # Stage 3: Execute actual registered CV capabilities.
        execution_result = pipeline.registry.execute_tasks(
            tasks=nlp_result["routing"]["tasks"],
            image_path=str(image_file),
            output_dir=str(task_output_dir),
        )

        execution_status = execution_result["execution_status"]

        final_status = (
            "success"
            if execution_status == "COMPLETED"
            else "failed"
        )

        return {
            "status": final_status,
            "run_id": run_id,
            "query": query,
            "nlp": nlp_result,
            "execution": execution_result,
        }
