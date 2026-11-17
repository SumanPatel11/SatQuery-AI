# Known Limitations and Future Work

## Current limitations

### Model and dataset distribution

Datasets, checkpoints, M1 tokenizer/configuration files, and generated outputs are excluded from Git. A source clone alone is insufficient to run all model-backed workflows. Local copies exist in the inspected workspace, but their provenance and redistribution permissions must be checked before publication or sharing.

### NLP and conversation

M1 and Qwen are probabilistic models; wording can affect classification and decomposition. Conversation memory is bounded, process-local, and lost on backend restart. It is not general-purpose long-term memory. Qwen rewrites are checked by a second Qwen call against a deterministic draft, but the check is not a formal entailment proof and can misjudge a paraphrase.

### CV measurement scope

- SpaceNet2 returns detections and counts; smoke counts are not accuracy.
- LoveDA reports class pixels; the application does not convert them to geospatial area.
- LEVIR-CD reports model-resolution changed pixels/fraction and requires matching input dimensions.
- Flood output consists of pixel counts and ratios from a two-band SAR raster, not physical area.
- Flood checks establish readability, band count, and size; they do not establish sensor provenance or calibration.

### Persistence and security

Analysis records and session state are in process memory. Uploads are written to backend storage, but the inspected application has no durable database or authentication. CORS is configured for local frontend origins; CORS is not access control. Do not deploy publicly without separate security, retention, and persistence work.

### Evaluation

Automated tests include mocked and contract cases. Recorded real model checks use selected samples only. No full-dataset evaluation or comparison is established by this documentation.

### Interface and API

The technical response can include local implementation/artifact details. Some request fields are accepted without affecting model selection; see [API Documentation](API_DOCUMENTATION.md).

## Future work

- Publish an artifact manifest with provenance and approved distribution locations; keep large artifacts outside ordinary Git history.
- Define reproducible, split-aware full-dataset evaluations and report metrics with protocol and limitations.
- Add durable session/analysis storage and authentication for deployed use.
- Validate flood sensor/modality metadata beyond raster band count and readability.
- Add geospatial area only when georeferencing and units are defined and validated.
- Capture genuine UI screenshots under `assets/screenshots/` with sample context.
- Use a separately validated semantic verifier if stronger factual guarantees are required than a second call to the same local LLM.
