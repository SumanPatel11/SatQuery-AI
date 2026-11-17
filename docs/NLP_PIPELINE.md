# NLP Pipeline

## Overview

The language stack converts a query into validated CV task identifiers; CV executors remain responsible for image measurements.

## M1: DistilBERT query attributes

`nlp/notebooks/models/nlu_model.py` loads a local tokenizer and fine-tuned checkpoint. The current configuration directory is `models/m1_distilbert/final_6_intent_balanced/`; it names `distilbert-base-uncased` and defines seven heads: `intent`, `target`, `attribute`, `ambiguity`, `spatial_relation`, `reference`, and `region`.

Tokenizer and base encoder loading use `local_files_only=True`; M1 inference is configured for CPU. M1 runs on the original query and on each M2-produced subquery. Local tokenizer/checkpoint files and the compatible base-model cache are required.

## M2: Query decomposition with Qwen3

`nlp/local_llm/m2_qwen.py` uses the local Ollama HTTP client and model tag `qwen3:1.7b`. It asks for JSON containing `subqueries` and a `combine` mode (`SINGLE` or `AND`). Its prompt uses conversation to resolve references and directs the model to preserve task semantics. Python code validates the returned shape and content.

## Task planner

`nlp/task_planner.py` asks Qwen3 to convert one subquery into a structured operation and target, with optional region and spatial-relation fields. It applies deterministic handling for known cases such as paired building change, flood semantics, and supported land-cover pixel statistics. Geographic land-cover area is unsupported because the current LoveDA output is pixel-based.

## Hybrid router

`nlp/query_router.py` maps operations and targets to canonical task names, consolidates tasks where one executor result can satisfy them, preserves operation information, and marks unsupported or conflicting tasks for review. Registered names include `BUILDING_DETECTION`, `LAND_COVER_DETECTION`, `BUILDING_CHANGE`, `FLOODED_AREA_DETECTION`, and `FLOODED_AREA_PRESENCE`.

## Capability validation and execution gate

`nlp/capability_registry.py` validates implementation files, model artifacts, and executor callability. The pipeline returns validation before CV execution. `backend/services/inference_service.py` blocks unavailable capabilities and inputs that fail task-specific checks.

## Conversational responses and reuse

The backend retains bounded session history in process memory and passes recent turns to M2. Compatible completed results can be reused for supported follow-up tasks. Explicit previous-result requests select a mentioned capability or, when no capability is named, use compatible results from that preceding multi-task analysis.

`integration/response_generator.py` builds an evidence-based deterministic draft. Qwen may rewrite it; a second Qwen call checks whether the rewrite preserves material meaning. Generation/review failures return the deterministic response. This model-based check can err and is not a formal entailment proof.

## Runtime dependency

Ollama must be reachable at the client default `http://localhost:11434`, and `qwen3:1.7b` must already be installed locally. No Ollama model is installed by the Python dependency file.
