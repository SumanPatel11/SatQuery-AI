# Installation and Local Runtime

## Requirements verified from repository files

- Python 3.14 CPU environment was used for the pinned backend dependencies in `requirements.txt`.
- Node.js `^20.19.0` or `>=22.12.0`, required by Vite in the frontend lockfile. The inspected local environment reported Node 24.21.0 and npm 11.19.0.
- Ollama running locally with the already-available `qwen3:1.7b` model tag.
- Local model checkpoints and M1 files listed below.

No model weights or datasets are downloaded by these setup instructions. Obtain and place artifacts separately through an approved process.

## Python backend

From the repository root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Direct pins include FastAPI, Uvicorn, Pydantic, PyTorch, Transformers, timm, Ultralytics, NumPy, Pillow, Rasterio, PyYAML, OpenCV, pytest, and httpx. Ollama is external and is not installed by pip.

## Frontend

```powershell
cd frontend
npm ci
```

`npm ci` uses `frontend/package-lock.json`. Actual scripts in `frontend/package.json` are `dev`, `build`, `lint`, `test`, and `preview`.

## Ollama and Qwen3

Start the already-installed Ollama service and verify the required model is present:

```powershell
ollama list
```

The client defaults to `http://localhost:11434` and uses model tag `qwen3:1.7b`. The repository does not include an Ollama installation or model-download step. Requests needing Qwen will fail if the service or tag is unavailable.

## Required local model files

Datasets, checkpoints, and M1 files are ignored by Git, so a source clone does not contain them by default:

- M1 configuration, fine-tuned checkpoint, and tokenizer assets under `models/m1_distilbert/final_6_intent_balanced/`; the local DistilBERT base model must also be available because loading is offline-only.
- SpaceNet2 checkpoint: `runs/detect/runs/detect/spacenet2_building_yolo26n/weights/best.pt`.
- LoveDA checkpoint: `models/cv/loveda_land_cover/best.pt`.
- LEVIR-CD V2 checkpoint: `models/cv/levir_cd_change_v2/best.pt`.
- Sen1Floods11 architecture and checkpoint: `models/cv/radiance_sen1floods11_v2/model.py` and `models/cv/radiance_sen1floods11_v2/best.pt`.

`cv/registry.py` checks implementation/artifact presence. Missing files make a capability unavailable; they are not fetched automatically.

## Run the application

Terminal 1, repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

The API client defaults to `http://localhost:8000`; `VITE_API_BASE_URL` can override it in local configuration.

## Input notes

- Building, land-cover, and change wrappers read image files through their respective implementations.
- Change analysis requires a before/after pair with matching dimensions.
- Flood detection requires a readable two-band SAR GeoTIFF at least 224 ? 224 pixels.
- A TIFF extension alone does not establish that it is a supported flood input.
