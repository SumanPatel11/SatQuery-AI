# Testing and Verification Report

## Automated tests

The latest recorded full-suite checks in the active working tree are:

| Suite | Result | Command |
|---|---:|---|
| Python | 69 passed, 1 skipped | `.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider` |
| Frontend | 17 passed, 0 failed | `npm.cmd test` from `frontend/` |

Python tests cover routing, capability registration, conversational behavior, overlay path validation, and lightweight CV contracts. Some CV contract cases mock model forwards; suite counts are not full-dataset evaluation. No model was retrained for these tests.

These counts record local development verification performed on 17 November 2026. Rerun them in an evaluation environment after required local artifacts and Ollama are provisioned.

## Recorded local smoke outputs

The prior local demo history records browser/API calls through checkpoint-backed executors. Values below are sample outputs, not evaluation metrics:

| Capability | Recorded sample output | Interpretation |
|---|---|---|
| SpaceNet2 building detection | 19 detections | Count for the selected demo image; not a precision, recall, or accuracy result |
| LoveDA land cover | Forest 121,424 pixels; agriculture 372,656 pixels; combined vegetation 494,080 pixels | Sample segmentation counts; a same-session follow-up reported 47.12% of valid image pixels |
| LEVIR-CD change | 126 changed pixels at 256 ? 256 model resolution (reported as 0.19226% pixel fraction) | Model-resolution output; not physical area or accuracy |
| Sen1Floods11 flood | 48,893 flood pixels; 101,623 valid pixels; 160,521 invalid pixels; 48.11% pixel fraction | Sample SAR inference; not geographic area or accuracy |

The prior demo history also records browser display of change and flood overlays. These observations were not repeated during documentation preparation. Counts depend on sample input and checkpoint.

## Not established by these checks

- Full-dataset benchmark scores for any capability.
- Generalization, calibration, or statistical confidence intervals.
- Production deployment, durable storage, or multi-worker session behavior.
- Formal correctness of Qwen's factual-equivalence judgment.
- Support for all image modalities, projections, or query formulations.

Do not interpret sample outputs as benchmark performance. No accuracy or IoU claim is made here.
