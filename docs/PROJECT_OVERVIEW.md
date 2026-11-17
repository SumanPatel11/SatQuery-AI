# Project Overview

## Purpose

SatQuery AI is a local-first prototype for asking natural-language questions about uploaded satellite images and routing supported requests to computer-vision models. It demonstrates integration of language understanding, task planning, capability validation, inference, and result presentation.

## What is implemented

- FastAPI endpoints accept uploads and analysis/query requests.
- M1 DistilBERT predicts seven configured query attributes: intent, target, attribute, ambiguity, spatial relation, reference, and region.
- M2 Qwen3 through Ollama decomposes a query; a Qwen-backed planner emits structured operations and targets.
- A hybrid router produces canonical task names, and a capability registry checks executor and artifact availability.
- Four CV executors are registered: SpaceNet2 building detection, LoveDA land-cover segmentation, LEVIR-CD change detection, and Sen1Floods11 flood detection.
- The response generator provides a Qwen rewrite subject to a factual-equivalence review, with a deterministic response on rejection or error.
- The React frontend uploads images, submits queries, and displays result summaries and available overlays.

?Implemented? describes source wiring and local demo behavior. It does not mean all inputs/questions are supported, that weights are included in Git, or that benchmark performance has been established.

## Main directory guide

- `backend/`: FastAPI application, route modules, upload and inference services.
- `nlp/`: M1 loader, Ollama/Qwen client, planner, router, and orchestration pipeline.
- `integration/`: conversational response generation and related integration helpers.
- `cv/models/`: model wrappers and inference executors.
- `cv/registry.py`: registration of model-backed capabilities.
- `cv/configs/`, `cv/preprocessing/`: model/dataset settings and data-preparation code.
- `frontend/`: React/Vite app, API clients, viewer, chat, and summary components.
- `tests/`: Python contract/integration tests; `frontend/tests/` contains Node tests.
- `data/`, `models/`, `runs/`, `cv/outputs/`: local data, checkpoints, and generated artifacts; excluded from normal Git tracking.
- `docs/`: explanatory project and contributor documentation.
- `assets/screenshots/`: location for genuine screenshots manually captured from the running app.

Historical audit reports and handoff snapshots remain in the workspace but are not primary runtime components.

## Evaluation boundaries

Reviewers can inspect source, tests, architecture, and result contracts. Running model-backed flows additionally requires local model artifacts and Ollama with `qwen3:1.7b`. Recorded smoke results are sample observations, not full-dataset metrics.
