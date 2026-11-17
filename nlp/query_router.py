from typing import Any, Dict, List


class HybridQueryRouter:

    VALID_OPERATIONS = {
        "COUNT", "DETECT", "LOCATE", "PRESENCE",
        "AREA", "CHANGE", "RELATIONSHIP", "UNSUPPORTED"
    }

    VALID_TARGETS = {
        "building", "road", "water", "vegetation",
        "forest", "agriculture", "flooded_area", "land_cover"
    }

    INTENT_TO_OPERATION = {
        "BUILDING_COUNT": "COUNT",
        "BUILDING_DETECTION": "DETECT",
        "BUILDING_CHANGE": "CHANGE",
        "LAND_COVER_ANALYSIS": "DETECT",
    }

    CANONICAL_TASK_NAMES = {
        ("flooded_area", "DETECT"): "FLOODED_AREA_DETECTION",
        ("flooded_area", "PRESENCE"): "FLOODED_AREA_PRESENCE",
        ("building", "DETECT"): "BUILDING_DETECTION",
        ("building", "COUNT"): "BUILDING_COUNT",
        ("building", "LOCATE"): "BUILDING_LOCATE",
        ("building", "CHANGE"): "BUILDING_CHANGE",
        ("land_cover", "DETECT"): "LAND_COVER_DETECTION",
        ("land_cover", "COUNT"): "LAND_COVER_DETECTION",
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

        # Consolidate paired-image building-change requests.
        if original_intent == "BUILDING_CHANGE" and len(planned_tasks) == 1:
            planned = planned_tasks[0]
            if planned.get("operation") != "CHANGE" or planned.get("target") != "building":
                raise ValueError("BUILDING_CHANGE must route to CHANGE on building.")
            source_subquery = planned.get("source_subquery")
            if not isinstance(source_subquery, str) or not source_subquery.strip():
                raise ValueError("Invalid building-change source query.")
            return {
                "original_intent": original_intent,
                "combine": m2_result.get("combine"),
                "execution_mode": "SINGLE_TASK",
                "tasks": [{
                    "source_subquery": source_subquery,
                    "operation": "CHANGE",
                    "target": "building",
                    "task": "BUILDING_CHANGE",
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

            if target in {"vegetation", "forest", "agriculture"}:
                target = "land_cover"

            requested_operation = operation
            # LoveDA's single segmentation executor returns both the seven
            # class mask and its class-wise pixel counts. Route COUNT through
            # that real capability instead of inventing LAND_COVER_COUNT.
            if target == "land_cover" and operation in {"DETECT", "COUNT", "LOCATE", "PRESENCE"}:
                operation = "DETECT"

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

            if target == "land_cover" and operation in {"AREA", "UNSUPPORTED"}:
                status = "NEEDS_REVIEW"
                task_name = "LAND_COVER_AREA_UNSUPPORTED"
            elif operation == "UNSUPPORTED" or target == "unknown":
                status = "NEEDS_REVIEW"
                # Keep a non-empty task identifier so registry validation can
                # report UNKNOWN/BLOCKED instead of raising a missing-name error.
                task_name = "UNSUPPORTED_TASK"
            else:
                status = "CANDIDATE"
                task_name = self.CANONICAL_TASK_NAMES.get(
                    (target, operation),
                    f"{target.upper()}_{operation}"
                )

            routed_task = {
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
            }
            if target == "land_cover" and requested_operation in {"DETECT", "COUNT", "LOCATE", "PRESENCE"}:
                routed_task["source_subqueries"] = [subquery]
                routed_task["requested_operations"] = [requested_operation]
            routed_tasks.append(routed_task)

        # Count, detect, and locate are views of the same SpaceNet2 output.
        # Run the shared detector once when the planner decomposes one query
        # into multiple building operations, while retaining requested intent.
        building_tasks = [
            task for task in routed_tasks
            if task.get("target") == "building"
            and task.get("task") in {
                "BUILDING_COUNT", "BUILDING_DETECTION", "BUILDING_LOCATE"
            }
        ]
        if len(building_tasks) > 1:
            consolidated_building = {
                **building_tasks[0],
                "operation": "DETECT",
                "task": "BUILDING_DETECTION",
                "source_subqueries": [
                    subquery
                    for task in building_tasks
                    for subquery in task.get(
                        "source_subqueries", [task["source_subquery"]]
                    )
                ],
                "requested_operations": [
                    operation
                    for task in building_tasks
                    for operation in task.get(
                        "requested_operations", [task["operation"]]
                    )
                ],
            }
            first_building_index = routed_tasks.index(building_tasks[0])
            routed_tasks = [
                task for task in routed_tasks
                if task not in building_tasks
            ]
            routed_tasks.insert(first_building_index, consolidated_building)

        # A decomposed request may ask for segmentation and class pixel counts
        # separately. Both are satisfied by one LoveDA inference, so validate
        # and execute the registered segmentation capability once.
        consolidated_tasks = []
        for task in routed_tasks:
            if task.get("task") != "LAND_COVER_DETECTION":
                consolidated_tasks.append(task)
                continue

            existing = next(
                (
                    item for item in consolidated_tasks
                    if item.get("task") == "LAND_COVER_DETECTION"
                ),
                None,
            )
            if existing is None:
                consolidated_tasks.append(task)
            else:
                existing["source_subqueries"].extend(
                    task.get("source_subqueries", [task["source_subquery"]])
                )
                existing["requested_operations"].extend(
                    task.get("requested_operations", [task["operation"]])
                )

        return {
            "original_intent": m1_result.get("intent"),
            "combine": m2_result.get("combine"),
            "execution_mode": (
                "SINGLE_TASK"
                if len(consolidated_tasks) == 1
                else "MULTI_TASK"
            ),
            "tasks": consolidated_tasks,
            "routing_status": "COMPLETED",
            "execution_status": "NOT_STARTED",
        }
