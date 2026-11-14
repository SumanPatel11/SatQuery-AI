from typing import Any, Dict, List


class HybridQueryRouter:

    VALID_OPERATIONS = {
        "COUNT", "DETECT", "LOCATE", "PRESENCE",
        "AREA", "CHANGE", "RELATIONSHIP", "UNSUPPORTED"
    }

    VALID_TARGETS = {
        "building", "road", "water", "vegetation",
        "flooded_area", "land_cover"
    }

    INTENT_TO_OPERATION = {
        "BUILDING_COUNT": "COUNT",
        "BUILDING_DETECTION": "DETECT",
        "BUILDING_CHANGE": "CHANGE",
        "LAND_COVER_ANALYSIS": "AREA",
    }

    CANONICAL_TASK_NAMES = {
        ("flooded_area", "DETECT"): "FLOODED_AREA_DETECTION",
        ("flooded_area", "PRESENCE"): "FLOODED_AREA_PRESENCE",
    }

    def route(
        self,
        m1_result: Dict[str, Any],
        m2_result: Dict[str, Any],
        subquery_m1_results: List[Dict[str, Any]],
        task_plan: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not isinstance(m1_result, dict):
            raise TypeError("Invalid original M1 result.")

        if not isinstance(m2_result, dict):
            raise TypeError("Invalid M2 result.")

        subqueries = m2_result.get("subqueries")
        planned_tasks = task_plan.get("tasks")

        if not isinstance(subqueries, list) or not subqueries:
            raise ValueError("M2 subqueries are missing.")

        if not isinstance(planned_tasks, list):
            raise ValueError("Task Planner tasks are missing.")

        if len(subqueries) != len(subquery_m1_results):
            raise ValueError("M1 subquery results count mismatch.")

        original_intent = m1_result.get("intent")

        # Handle a consolidated single-task flood query.
        if (
            original_intent == "FLOOD_DETECTION"
            and len(planned_tasks) == 1
            and len(subqueries) >= 1
        ):
            planned = planned_tasks[0]

            operation = planned.get("operation")
            target = planned.get("target")
            source_subquery = planned.get("source_subquery")

            if operation not in {"DETECT", "PRESENCE"}:
                raise ValueError("Invalid consolidated flood operation.")

            if target != "flooded_area":
                raise ValueError("Invalid consolidated flood target.")

            if not isinstance(source_subquery, str) or not source_subquery.strip():
                raise ValueError("Invalid consolidated flood source.")

            task_name = self.CANONICAL_TASK_NAMES[(target, operation)]

            return {
                "original_intent": original_intent,
                "combine": m2_result.get("combine"),
                "execution_mode": "SINGLE_TASK",
                "tasks": [{
                    "source_subquery": source_subquery,
                    "operation": operation,
                    "target": target,
                    "task": task_name,
                    "region": planned.get("region", "none"),
                    "spatial_relation": planned.get("spatial_relation", "none"),
                    "m1_intent": original_intent,
                    "original_intent": original_intent,
                    "m1_intent_disagreement": False,
                    "m1_intent_alignment": "ALIGNED",
                    "status": "CANDIDATE",
                }],
                "routing_status": "COMPLETED",
                "execution_status": "NOT_STARTED",
            }

        if len(subqueries) != len(planned_tasks):
            raise ValueError("Task Planner result count mismatch.")

        routed_tasks = []

        for subquery, m1_subquery, planned in zip(
            subqueries, subquery_m1_results, planned_tasks
        ):
            operation = planned.get("operation")
            target = planned.get("target")

            if operation not in self.VALID_OPERATIONS:
                raise ValueError("Invalid planned operation.")

            if target not in self.VALID_TARGETS | {"unknown"}:
                raise ValueError("Invalid planned target.")

            if planned.get("source_subquery") != subquery:
                raise ValueError("Source subquery mismatch.")

            m1_intent = m1_subquery.get("intent")
            original_intent = m1_result.get("intent")

            expected_operation = self.INTENT_TO_OPERATION.get(
                m1_intent
            )

            conflict = (
                expected_operation is not None
                and operation != expected_operation
            )

            if operation == "UNSUPPORTED" or target == "unknown":
                status = "NEEDS_REVIEW"
                task_name = None
            else:
                status = "CANDIDATE"
                task_name = self.CANONICAL_TASK_NAMES.get(
                    (target, operation),
                    f"{target.upper()}_{operation}"
                )

            routed_tasks.append({
                "source_subquery": subquery,
                "operation": operation,
                "target": target,
                "task": task_name,
                "region": planned.get("region", "none"),
                "spatial_relation": planned.get(
                    "spatial_relation", "none"
                ),
                "m1_intent": m1_intent,
                "original_intent": original_intent,
                "m1_intent_disagreement": conflict,
                "m1_intent_alignment": (
                    "DIFFERENT" if conflict else "ALIGNED"
                ),
                "status": status,
            })

        return {
            "original_intent": m1_result.get("intent"),
            "combine": m2_result.get("combine"),
            "execution_mode": (
                "SINGLE_TASK"
                if len(routed_tasks) == 1
                else "MULTI_TASK"
            ),
            "tasks": routed_tasks,
            "routing_status": "COMPLETED",
            "execution_status": "NOT_STARTED",
        }
