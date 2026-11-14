"""Qwen3-based M2 query rewriting for SatQuery AI."""

import json
import re
from typing import Any, Dict, List, Optional, Sequence

from .ollama_client import OllamaClient


class M2Qwen:

    DEFAULT_MODEL = "qwen3:1.7b"

    VALID_COMBINE_OPERATIONS = {"SINGLE", "AND"}

    OUTPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "subqueries": {
                "type": "array",
                "items": {"type": "string"}
            },
            "combine": {
                "type": "string",
                "enum": ["SINGLE", "AND"]
            }
        },
        "required": ["subqueries", "combine"],
        "additionalProperties": False
    }

    SYSTEM_PROMPT = """
You are SatQuery AI M2, a satellite image query rewriting
and task decomposition engine.

OBJECTIVE:
Interpret the CURRENT USER QUERY using the supplied conversation
context. Produce complete standalone satellite image analysis tasks.

CONTEXT AND TASK SELECTION:

1. The current query is the primary instruction.
2. Use conversation context only to resolve incomplete references,
   pronouns, ellipsis and explicitly continuing tasks.
3. Do not repeat an earlier task merely because it appears in context.
3a. When the current query starts with "And" and introduces a new
    object, treat it as a new task for that object only. Do not
    repeat the previous object's task unless explicitly requested.
4. If the current query introduces a new independent task with
   "also", "additionally" or equivalent wording, preserve the
   relevant active task when the conversation clearly indicates
   that both tasks are requested together.
5. If the current query replaces or changes an earlier task,
   output only the updated task.
6. Never introduce an unrelated earlier task.
7. Resolve pronouns such as they, them, it and those using the
   most relevant entity in conversation context.
8. Resolve phrases such as "and water?", "what about the south?"
   and "near it?" using context without duplicating completed tasks.
9. If no context is provided, interpret the current query independently.

TASK SEMANTICS:

10. Preserve the exact operation requested:
    - Locate / Where: identify the spatial location of an object.
    - Count / How many: count objects.
    - Presence / Whether: determine whether an object exists.
    - Area / How much / What fraction / What percentage:
      calculate area or percentage as requested.
    - Relationship / Near: evaluate the specified spatial relation.
11. Never replace counting with locating or presence detection.
12. Never replace locating with presence detection.
13. Never replace area or percentage calculation with counting.
14. Do not invent a measurement type, object, region or relationship.
15. Preserve spatial references such as north, south, east, west,
    top, bottom, left, right, center and near.
16. Preserve distinctions between area and percentage.
    Do not convert one into the other unless the query requests it.
17. Split multiple independent requested operations into separate
    subqueries.
18. Do not split one operation into multiple artificial tasks.

OUTPUT RULES:

19. Every subquery must be a complete standalone natural-language
    satellite image analysis instruction.
20. Use SINGLE for exactly one task.
21. Use AND for two or more independent tasks.
22. SINGLE must contain exactly one subquery.
23. AND must contain at least two subqueries.
24. Do not output SQL, Python, code, function calls, pseudocode,
    isolated words or explanations.
25. Never invent objects, locations, counts or measurements.
26. Return only JSON matching the required schema.

EXAMPLES:

Example 1 - Ellipsis:
Previous: Is road present?
Current: And water?
Output:
{"subqueries":["Determine whether water is present in the image."],"combine":"SINGLE"}

Example 1b - New object in an ellipsis:
Previous: Where are the buildings?
Current: And the roads?
Output:
{"subqueries":["Locate the roads in the image."],"combine":"SINGLE"}

Example 2 - Pronoun:
Previous: Locate the buildings.
Current: How many of them?
Output:
{"subqueries":["Count the buildings in the image."],"combine":"SINGLE"}

Example 3 - Spatial context:
Previous: Count buildings in the north.
Current: What about the south?
Output:
{"subqueries":["Count the buildings in the south region of the image."],"combine":"SINGLE"}

Example 4 - Multiple tasks:
Previous: None
Current: Count buildings and locate roads.
Output:
{"subqueries":["Count the buildings in the image.","Locate the roads in the image."],"combine":"AND"}

Example 5 - Percentage:
Previous: None
Current: What fraction of the image is water?
Output:
{"subqueries":["Calculate the percentage of the image covered by water."],"combine":"SINGLE"}

Example 6 - Preserve previous task with explicit addition:
Previous: Determine whether buildings are present.
Current: Also calculate the vegetation area.
Output:
{"subqueries":["Determine whether buildings are present in the image.","Calculate the area covered by vegetation in the image."],"combine":"AND"}

Example 7 - Spatial relationship:
Previous: Locate the roads.
Current: Are they near the water?
Output:
{"subqueries":["Determine whether the roads are near the water in the image."],"combine":"SINGLE"}

Example 8 - Location only:
Previous: None
Current: Locate the roads.
Output:
{"subqueries":["Locate the roads in the image."],"combine":"SINGLE"}

Example 9 - Replace region:
Previous: Count buildings in the north.
Current: What about the south?
Output:
{"subqueries":["Count the buildings in the south region of the image."],"combine":"SINGLE"}
"""

    def __init__(
        self,
        client: Optional[OllamaClient] = None,
        model: str = DEFAULT_MODEL,
        timeout: int = 180,
    ):
        self.client = client or OllamaClient(timeout=timeout)
        self.model = model

    @staticmethod
    def build_input(
        current_query: str,
        conversation: Optional[Sequence[str]] = None,
    ) -> str:

        query = str(current_query).strip()

        if not query:
            raise ValueError("current_query cannot be empty.")

        context_lines = []

        if conversation:
            for index, message in enumerate(conversation, start=1):
                message = str(message).strip()

                if message:
                    context_lines.append(f"{index}. {message}")

        context = (
            "\n".join(context_lines)
            if context_lines
            else "No previous conversation."
        )

        return (
            f"Previous conversation:\n{context}\n\n"
            f"Current user query:\n{query}"
        )

    @classmethod
    def validate_output(
        cls,
        obj: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not isinstance(obj, dict):
            raise ValueError("M2 output must be a JSON object.")

        if set(obj.keys()) != {"subqueries", "combine"}:
            raise ValueError(
                "M2 output must contain only subqueries and combine."
            )

        subqueries = obj["subqueries"]
        combine = obj["combine"]

        if not isinstance(subqueries, list) or not subqueries:
            raise ValueError("subqueries must be a non-empty list.")

        if not isinstance(combine, str):
            raise ValueError("combine must be a string.")

        combine = combine.strip().upper()

        if combine not in cls.VALID_COMBINE_OPERATIONS:
            raise ValueError(f"Invalid combine operation: {combine}")

        cleaned = []

        for query in subqueries:
            if not isinstance(query, str):
                raise ValueError("Every subquery must be a string.")

            query = re.sub(r"\s+", " ", query).strip()

            if len(query) < 10:
                raise ValueError(
                    f"Subquery is incomplete or too short: {query!r}"
                )

            if re.search(
                r"(?i)\b(SELECT\s+|INSERT\s+INTO|UPDATE\s+\w+\s+SET|"
                r"DELETE\s+FROM|def\s+\w+|function\s+\w+|"
                r"get_count\s*\(|COUNT\s*\(\s*\*|"
                r"return\s+\w+)\b",
                query,
            ):
                raise ValueError(
                    f"Code-like output is not allowed: {query!r}"
                )

            if not re.search(r"[A-Za-z]", query):
                raise ValueError("Subquery must contain natural language.")

            cleaned.append(query)

        if combine == "SINGLE" and len(cleaned) != 1:
            raise ValueError(
                "SINGLE must contain exactly one subquery."
            )

        if combine == "AND" and len(cleaned) < 2:
            raise ValueError(
                "AND must contain at least two subqueries."
            )

        return {
            "subqueries": cleaned,
            "combine": combine,
        }

    @classmethod
    def parse_output(cls, generated_text: str) -> Dict[str, Any]:

        try:
            obj = json.loads(generated_text)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(
                "M2 generated invalid JSON."
            ) from exc

        return cls.validate_output(obj)

    def predict_with_raw_output(
        self,
        current_query: str,
        conversation: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:

        user_input = self.build_input(
            current_query=current_query,
            conversation=conversation,
        )

        messages = [
            {
                "role": "system",
                "content": self.SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_input,
            },
        ]

        raw_output = self.client.chat(
            model=self.model,
            messages=messages,
            format_schema=self.OUTPUT_SCHEMA,
            temperature=0,
        )

        parsed = self.parse_output(raw_output)

        return {
            "input": user_input,
            "raw_output": raw_output,
            "result": parsed,
        }

    def predict(
        self,
        current_query: str,
        conversation: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:

        output = self.predict_with_raw_output(
            current_query=current_query,
            conversation=conversation,
        )

        return output["result"]


if __name__ == "__main__":

    model = M2Qwen()

    result = model.predict_with_raw_output(
        current_query="And water?",
        conversation=["Is road present?"],
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
