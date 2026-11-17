
import json
import re
from typing import Any, Dict, List

from nlp.local_llm.ollama_client import OllamaClient
from nlp.local_llm.m2_qwen import M2Qwen


class TaskPlanner:

    OPERATIONS = [
        "COUNT", "DETECT", "LOCATE", "PRESENCE",
        "AREA", "CHANGE", "RELATIONSHIP", "UNSUPPORTED",
    ]

    TARGETS = [
        "building", "road", "water", "vegetation",
        "forest", "agriculture", "flooded_area", "land_cover", "unknown",
    ]

    OUTPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": OPERATIONS,
            },
            "target": {
                "type": "string",
                "enum": TARGETS,
            },
            "region": {"type": "string"},
            "spatial_relation": {"type": "string"},
        },
        "required": [
            "operation", "target", "region", "spatial_relation"
        ],
        "additionalProperties": False,
    }

    SYSTEM_PROMPT = """
You are the SatQuery AI Task Planner.

Convert ONE satellite image analysis subquery into ONE
structured CV task specification.

OPERATIONS:
- COUNT: Count objects.
- DETECT: Detect or identify objects.
- LOCATE: Find spatial locations of objects.
- PRESENCE: Determine whether an object exists.
- AREA: Calculate area, fraction or percentage.
- CHANGE: Analyze changes between observations.
- RELATIONSHIP: Evaluate spatial relationships.
- UNSUPPORTED: Operation cannot be represented.

RULES:
1. Process only the supplied subquery.
2. Return exactly one task specification.
3. COUNT and DETECT are different.
4. LOCATE and PRESENCE are different.
5. AREA and COUNT are different.
6. Preserve the requested target.
7. Preserve explicit region and spatial relationships.
8. Never invent a target, region or relationship.
9. Use unknown when the target is unclear.
10. Return only JSON matching the schema.

FLOOD SEMANTICS:
- Flood detection and ordinary water presence are different tasks.
- When the original M1 intent is FLOOD_DETECTION,
  use flooded_area as the target.
- For requests to detect or identify flooded areas,
  use DETECT with flooded_area.
- For requests explicitly asking whether flooding exists,
  use PRESENCE with flooded_area.
- Do not convert flood detection into ordinary water presence.
        - LoveDA returns class pixel counts from one segmentation result.
        - Image pixel counts, fractions and percentages may be derived from
          segmentation; do not describe them as geographic area.
        - Geographic/physical area (for example hectares or square kilometres)
          is unsupported and must use AREA with target land_cover.
- Use DETECT for land-cover segmentation/classification requests.

EXAMPLES:
Count the buildings in the image.
=> COUNT, building

Locate the roads in the image.
=> LOCATE, road

Determine whether water is present in the image.
=> PRESENCE, water

Calculate the percentage of image pixels covered by vegetation.
=> DETECT, land_cover

Calculate the geographic area of forest in hectares.
=> AREA, land_cover

Detect buildings in the image.
=> DETECT, building

Detect flooded areas in the image.
=> DETECT, flooded_area
"""

    def __init__(self, client=None, model=M2Qwen.DEFAULT_MODEL):
        self.client = client or OllamaClient()
        self.model = model

    @staticmethod
    def _is_explicit_presence_query(query: str) -> bool:
        text = query.lower().strip()

        patterns = (
            r"\b(is|are)\s+(there|any)\b",
            r"\bwhether\b",
            r"\bpresent\b",
            r"\bpresence\b",
            r"\bexists?\b",
        )

        return any(re.search(pattern, text) for pattern in patterns)

    @staticmethod
    def _is_explicit_multi_task_query(query: str) -> bool:
        text = query.lower()

        # Preserve clearly independent operations joined by
        # explicit conjunctions. A generic "and" alone is not
        # sufficient to establish multiple tasks.
        patterns = (
            r"\bcount\b.+\band\b.+\b(locate|detect|identify)\b",
            r"\b(locate|detect|identify)\b.+\band\b.+\bcount\b",
            r"\balso\b",
            r"\badditionally\b",
        )

        return any(re.search(pattern, text) for pattern in patterns)

    @staticmethod
    def _normalize_land_cover_task(
        subquery: str,
        task: Dict[str, Any],
        subquery_intent: str = "",
        original_query: str = "",
    ) -> Dict[str, Any]:
        """Map vegetation/class questions onto the existing LoveDA segmentation."""
        text = subquery.lower()
        target = str(task.get("target", "")).lower()
        land_cover_request = (
            target in {"vegetation", "forest", "agriculture", "land_cover"}
            or subquery_intent == "LAND_COVER_ANALYSIS"
            or re.search(r"\b(vegetation|forest|forests|agricultur\w*|land[ -]cover)\b", text)
        )
        if not land_cover_request:
            return task

        normalized = dict(task)
        normalized["target"] = "land_cover"
        normalized["region"] = "none"
        normalized["spatial_relation"] = "none"

        original_text = original_query.lower()
        semantic_text = f"{text} {original_text}"
        explicit_physical_units = bool(re.search(
            r"\b(hectares?|acres?|square\s*(kilomet(?:er|re)s?|miles?|met(?:er|re)s?)|sq\.?\s*(km|mi|m)|geographic(?:al)?\s+area|physical\s+area)\b",
            semantic_text,
        ))
        pixel_stat_pattern = r"\b(pixel|pixels|count|counts|how\s+much|percentage|percent|fraction|coverage|covered)\b"
        original_requests_pixel_stat = bool(re.search(pixel_stat_pattern, original_text))
        original_requests_area = bool(re.search(r"\barea\b", original_text))
        subquery_requests_area = bool(re.search(r"\barea\b", text))
        subquery_requests_pixel_stat = bool(re.search(pixel_stat_pattern, text))
        physical_area = explicit_physical_units or (
            original_requests_area and not original_requests_pixel_stat
        ) or (
            not original_requests_area
            and not original_requests_pixel_stat
            and subquery_requests_area
            and not subquery_requests_pixel_stat
        )

        if physical_area:
            normalized["operation"] = "AREA"
        elif re.search(r"\b(count|counts|how\s+much)\b", semantic_text):
            normalized["operation"] = "COUNT"
        else:
            # Segmentation supplies the actual class mask/counts; pixel
            # percentages are derived from this same inference result.
            normalized["operation"] = "DETECT"
        return normalized

    def plan(
        self,
        original_query: str,
        m1_result: Dict[str, Any],
        m2_result: Dict[str, Any],
        subquery_m1_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        subqueries = m2_result.get("subqueries", [])

        if not isinstance(subqueries, list) or not subqueries:
            raise ValueError("M2 returned no valid subqueries.")

        if len(subqueries) != len(subquery_m1_results):
            raise ValueError(
                "Each subquery must have one corresponding M1 result."
            )

        original_intent = m1_result.get("intent")

        # Preserve BUILDING_CHANGE as one paired-image task. M2 may
        # split the wording into before/after locate requests, but the
        # Siamese change model compares both images jointly.
        if (
            original_intent == "BUILDING_CHANGE"
            and not self._is_explicit_multi_task_query(original_query)
        ):
            return {
                "tasks": [{
                    "source_subquery": original_query,
                    "operation": "CHANGE",
                    "target": "building",
                    "region": "none",
                    "spatial_relation": "none",
                }]
            }

        # Correct M2 over-decomposition for a single flood request.
        # Preserve multiple tasks only when the original query
        # explicitly requests independent operations.
        if (
            original_intent == "FLOOD_DETECTION"
            and not self._is_explicit_multi_task_query(original_query)
        ):
            operation = (
                "PRESENCE"
                if self._is_explicit_presence_query(original_query)
                else "DETECT"
            )

            return {
                "tasks": [{
                    "source_subquery": original_query,
                    "operation": operation,
                    "target": "flooded_area",
                    "region": "none",
                    "spatial_relation": "none",
                }]
            }

        planned_tasks = []

        for subquery, prediction in zip(
            subqueries, subquery_m1_results
        ):

            if not isinstance(subquery, str) or not subquery.strip():
                raise ValueError("Invalid M2 subquery.")

            payload = {
                "original_query": original_query,
                "original_m1_intent": original_intent,
                "subquery": subquery,
                "m1_subquery_intent": prediction.get("intent"),
                "m1_predictions": prediction.get("predictions", {}),
            }

            raw = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self.SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            payload, ensure_ascii=False
                        ),
                    },
                ],
                format_schema=self.OUTPUT_SCHEMA,
                temperature=0,
            )

            try:
                task = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Task Planner returned invalid JSON."
                ) from exc

            if not isinstance(task, dict):
                raise ValueError("Invalid task specification.")

            operation = task.get("operation")
            target = task.get("target")

            if operation not in self.OPERATIONS:
                raise ValueError("Invalid task operation.")

            if target not in self.TARGETS:
                raise ValueError("Invalid task target.")

            task = self._normalize_land_cover_task(
                subquery,
                task,
                prediction.get("intent", ""),
                original_query,
            )
            operation = task["operation"]
            target = task["target"]

            for field in ("region", "spatial_relation"):
                if not isinstance(task.get(field), str):
                    raise ValueError(
                        f"Invalid task field: {field}"
                    )

            planned_tasks.append({
                "source_subquery": subquery,
                "operation": operation,
                "target": target,
                "region": task["region"],
                "spatial_relation": task["spatial_relation"],
            })

        return {"tasks": planned_tasks}
