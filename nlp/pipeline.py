from typing import Optional, Sequence

from nlp.notebooks.models.nlu_model import M1Predictor
from nlp.local_llm.m2_qwen import M2Qwen
from nlp.task_planner import TaskPlanner
from nlp.query_router import HybridQueryRouter
from nlp.capability_registry import CapabilityRegistry
from cv.registry import create_capability_registry


class SatQueryNLPPipeline:
    """M1 + M2 + Task Planner + Router + Capability Validation."""

    def __init__(
        self,
        m1: Optional[M1Predictor] = None,
        m2: Optional[M2Qwen] = None,
        planner: Optional[TaskPlanner] = None,
        router: Optional[HybridQueryRouter] = None,
        registry: Optional[CapabilityRegistry] = None,
    ):
        self.m1 = m1 or M1Predictor()
        self.m2 = m2 or M2Qwen()
        self.planner = planner or TaskPlanner()
        self.router = router or HybridQueryRouter()
        self.registry = registry if registry is not None else create_capability_registry()

    def process_query(
        self,
        query: str,
        conversation: Optional[Sequence[str]] = None,
    ) -> dict:

        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string.")

        # Stage 1: Original query understanding
        m1_result = self.m1.predict(query)

        # Stage 2: Query decomposition
        m2_result = self.m2.predict(
            current_query=query,
            conversation=conversation,
        )

        # Stage 3: M1 classification for each subquery
        subquery_m1_results = [
            self.m1.predict(subquery)
            for subquery in m2_result["subqueries"]
        ]

        # Stage 4: Qwen3 task planning
        task_plan = self.planner.plan(
            original_query=query,
            m1_result=m1_result,
            m2_result=m2_result,
            subquery_m1_results=subquery_m1_results,
        )

        # Stage 5: Hybrid routing
        routing_result = self.router.route(
            m1_result=m1_result,
            m2_result=m2_result,
            subquery_m1_results=subquery_m1_results,
            task_plan=task_plan,
        )

        # Stage 6: Verify actual CV capabilities
        capability_result = self.registry.validate_tasks(
            routing_result["tasks"]
        )

        return {
            "original_query": query,
            "m1": m1_result,
            "m2": m2_result,
            "subquery_m1_results": subquery_m1_results,
            "task_plan": task_plan,
            "routing": routing_result,
            "capability_validation": capability_result,
            "status": "success",
        }


if __name__ == "__main__":
    import json

    pipeline = SatQueryNLPPipeline()

    result = pipeline.process_query(
        query="Count buildings and locate roads in the image.",
        conversation=[],
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

