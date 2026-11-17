"""Evidence-grounded conversational responses for SatQuery analyses."""

import json
import logging
import re
from typing import Any, Dict, Optional

from nlp.local_llm.m2_qwen import M2Qwen
from nlp.local_llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}

GROUNDING_SCHEMA = {
    "type": "object",
    "properties": {"preserves_meaning": {"type": "boolean"}},
    "required": ["preserves_meaning"],
    "additionalProperties": False,
}

_NUMBER = re.compile(r"(?<![A-Za-z])\d+(?:,\d{3})*(?:\.\d+)?%?")
_INTERNAL_PATH = re.compile(r"(?:[A-Za-z]:\\|\\\\[^\\]+\\|/home/|/mnt/)")
_SPATIAL_FOLLOWUP = re.compile(
    r"\b(concentrat\w*|cluster\w*|spread|distribution|grouped|area)\b"
    r"|\b(they|them|those|these)\b",
    re.IGNORECASE,
)


def _results(execution: Optional[Dict[str, Any]]):
    if not isinstance(execution, dict):
        return []
    return [
        item for item in execution.get("results", [])
        if isinstance(item, dict) and isinstance(item.get("result"), dict)
    ]


def build_fallback_response(
    query: str,
    status: str,
    execution: Optional[Dict[str, Any]],
    context_resolution: Optional[Dict[str, Any]] = None,
) -> str:
    """Create concise text using only values present in the API result."""
    if context_resolution and context_resolution.get("spatial_distribution"):
        distribution = context_resolution["spatial_distribution"]
        total = distribution.get("detection_count", 0)
        if total == 0:
            return "The previous model result contained no building detections to compare spatially."
        largest = distribution.get("largest_region") or {}
        return (
            f"I checked the locations of the {total} buildings detected earlier. "
            f"The largest image grid region is {largest.get('label', 'unavailable')}, "
            f"with {largest.get('count', 0)} detection centers. "
            "This is a pixel-grid summary of the returned boxes, not a geographic-area measurement."
        )

    if status == "blocked":
        validation = (execution or {}).get("validation", {})
        reason = validation.get("reason")
        if not reason:
            reason = next(
                (task.get("reason") for task in validation.get("tasks", []) if task.get("reason")),
                None,
            )
        return reason or "I can’t answer that from the available analysis capabilities. Could you rephrase the request?"

    if status != "success":
        return "I couldn’t complete the image analysis. Please check the input and try again."

    answers = []
    for item in _results(execution):
        result = item["result"]
        capability = item.get("task") or result.get("capability")
        if item.get("error"):
            answers.append(str(item["error"]))
        elif capability in {"BUILDING_DETECTION", "BUILDING_COUNT", "BUILDING_LOCATE"}:
            count = result.get("building_count")
            if isinstance(count, int) and count >= 0:
                if count:
                    answers.append(
                        f"I found {count} building detections in this image. "
                        "Their returned locations are marked in the viewer."
                    )
                else:
                    answers.append(
                        "I couldn’t identify any buildings in this image using the model’s current output."
                    )
        elif capability == "LAND_COVER_DETECTION":
            counts = result.get("class_pixel_counts") or {}
            vegetation = result.get("vegetation_pixel_summary") or {}
            if re.search(r"\b(vegetation|forest|agricultur)\w*\b", query, re.I):
                forest = vegetation.get("forest_pixels", counts.get("forest"))
                agriculture = vegetation.get("agriculture_pixels", counts.get("agriculture"))
                parts = []
                if isinstance(forest, int):
                    parts.append(f"forest: {forest:,} pixels")
                if isinstance(agriculture, int):
                    parts.append(f"agriculture: {agriculture:,} pixels")
                total = vegetation.get("total_vegetation_pixels")
                percentage = vegetation.get("vegetation_pixel_percentage")
                if isinstance(total, int) and re.search(r"\b(total|how much|coverage|covered|count)\b", query, re.I):
                    parts.append(f"total vegetation: {total:,} pixels")
                if isinstance(percentage, (int, float)) and re.search(r"\b(percent|percentage|fraction|coverage|covered)\b", query, re.I):
                    parts.append(f"{percentage:.2f}% of valid image pixels")
                if parts:
                    answers.append("The land-cover segmentation is complete. It reports " + "; ".join(parts) + ". These are image-pixel measurements.")
            elif counts:
                classes = ", ".join(
                    f"{name}: {value:,} pixels"
                    for name, value in counts.items()
                    if isinstance(value, int) and value >= 0
                )
                answers.append("The land-cover segmentation is complete. The returned class pixel counts are " + classes + ".")
        elif capability == "BUILDING_CHANGE":
            changed = result.get("changed_pixels_at_model_resolution")
            fraction = result.get("changed_fraction_at_model_resolution")
            if isinstance(changed, int):
                answer = f"The comparison is complete. The model marked {changed:,} changed pixels at its output resolution."
                if isinstance(fraction, (int, float)):
                    answer += f" That is a {fraction * 100:.2f}% image-pixel fraction, not accuracy or geographic area."
                answers.append(answer)
        elif capability in {"FLOODED_AREA_DETECTION", "FLOODED_AREA_PRESENCE"}:
            flood = result.get("flood_pixels")
            valid = result.get("valid_pixels")
            invalid = result.get("invalid_pixels")
            fraction = result.get("flood_area_pixel_fraction")
            if isinstance(flood, int) and isinstance(valid, int):
                answer = f"The SAR flood analysis found {flood:,} flood pixels among {valid:,} valid pixels"
                if isinstance(invalid, int):
                    answer += f"; {invalid:,} pixels were invalid"
                answer += "."
                if isinstance(fraction, (int, float)):
                    answer += f" The flood pixel fraction is {fraction * 100:.2f}%, not geographic area."
                answers.append(answer)

    if answers:
        return " ".join(answers)
    return "The analysis completed, but the returned result does not contain the measurement needed to answer that question."


def _evidence(execution: Optional[Dict[str, Any]], context_resolution=None):
    compact = []
    for item in _results(execution):
        result = item["result"]
        keys = (
            "capability", "model", "device", "image_width", "image_height",
            "building_count", "class_pixel_counts",
            "vegetation_pixel_summary", "changed_pixels_at_model_resolution",
            "total_pixels_at_model_resolution", "changed_fraction_at_model_resolution",
            "flood_pixels", "valid_pixels", "invalid_pixels", "flood_area_pixel_fraction",
            "spatial_distribution",
        )
        facts = {key: result[key] for key in keys if key in result}
        facts["task"] = item.get("task")
        if item.get("error"):
            facts["error"] = item["error"]
        compact.append(facts)
    if context_resolution:
        compact.append({"context_resolution": context_resolution})
    return compact


def _is_grounded(candidate: str, fallback: str) -> bool:
    """Apply format and disclosure checks before semantic review."""
    if not candidate or len(candidate) > 700 or _INTERNAL_PATH.search(candidate):
        return False
    if candidate.lstrip().startswith(("{", "```")):
        return False
    return len(re.findall(r"\b[A-Za-z]{2,}\b", candidate)) >= 4


class ResponseGenerator:
    """Use the existing local Qwen3 service, with an evidence-safe fallback."""

    SYSTEM_PROMPT = (
        "You are SatQuery AI, a concise conversational assistant for satellite-image analysis. "
        "Rewrite the supplied evidence-based draft naturally without changing its meaning. "
        "The draft and structured CV evidence are the only sources of facts. "
        "Do not add observations, entities, locations, counts, confidence, accuracy, or area claims. "
        "Keep every number exactly supported by the draft. Do not mention file paths or JSON. "
        "Return only an object with one string field named answer."
    )

    GROUNDING_PROMPT = (
        "You are a strict factual-equivalence reviewer. Compare a candidate response with the grounded draft. "
        "Return preserves_meaning=true only if the candidate preserves every material fact and qualification "
        "from the draft and adds no factual claim unsupported by the draft or supplied evidence. "
        "Natural paraphrases, synonyms, and numbers written as words are acceptable when their meaning is the same. "
        "Reject changed, omitted, overstated, or newly added counts, entities, locations, measurements, certainty, "
        "or interpretations. Ignore style and politeness. Do not use outside knowledge or conversation history. "
        "Return only the required JSON object."
    )

    def __init__(self, client: Optional[OllamaClient] = None, model: str = M2Qwen.DEFAULT_MODEL):
        self.client = client or OllamaClient(timeout=45)
        self.model = model

    def _preserves_meaning(self, answer: str, fallback: str, evidence) -> bool:
        raw = self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": self.GROUNDING_PROMPT},
                {"role": "user", "content": json.dumps({
                    "grounded_draft": fallback,
                    "candidate_response": answer,
                    "structured_evidence": evidence,
                }, ensure_ascii=False)},
            ],
            format_schema=GROUNDING_SCHEMA,
            temperature=0,
        )
        parsed = json.loads(raw)
        return (
            isinstance(parsed, dict)
            and set(parsed) == {"preserves_meaning"}
            and type(parsed.get("preserves_meaning")) is bool
            and parsed["preserves_meaning"] is True
        )

    def generate(
        self,
        query: str,
        status: str,
        execution: Optional[Dict[str, Any]],
        nlp: Optional[Dict[str, Any]] = None,
        conversation=None,
        context_resolution=None,
    ) -> Dict[str, str]:
        fallback = build_fallback_response(query, status, execution, context_resolution)
        if status != "success":
            return {"answer": fallback, "status": "DETERMINISTIC_FALLBACK", "model": None}
        payload = {
            "current_query": query,
            "recent_conversation": list(conversation or [])[-8:],
            "m1_predictions": (nlp or {}).get("m1", {}).get("predictions", {}),
            "execution_status": status,
            "evidence": _evidence(execution, context_resolution),
            "grounded_draft": fallback,
        }
        try:
            raw = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                format_schema=ANSWER_SCHEMA,
                temperature=0,
            )
            parsed = json.loads(raw)
            answer = parsed.get("answer") if isinstance(parsed, dict) else None
            if not isinstance(answer, str) or not _is_grounded(answer.strip(), fallback):
                raise ValueError("Qwen response did not pass response-format validation.")
            answer = answer.strip()
            if not self._preserves_meaning(answer, fallback, payload["evidence"]):
                raise ValueError("Qwen response did not preserve the grounded draft's factual meaning.")
            return {"answer": answer, "status": "GENERATED", "model": self.model}
        except Exception:
            logger.exception("Qwen response generation failed; using grounded fallback")
            return {"answer": fallback, "status": "FALLBACK", "model": self.model}
