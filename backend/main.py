from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from backend.services.inference_service import SatQueryInferenceService

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "storage" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 20 * 1024 * 1024

_inference_service = None
_analysis_records = {}
_analysis_order = []

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"
}

IMAGE_SIGNATURES = {
    ".jpg": lambda d: d.startswith(b"\xff\xd8\xff"),
    ".jpeg": lambda d: d.startswith(b"\xff\xd8\xff"),
    ".png": lambda d: d.startswith(b"\x89PNG\r\n\x1a\n"),
    ".webp": lambda d: len(d) >= 12 and d[:4] == b"RIFF" and d[8:12] == b"WEBP",
    ".tif": lambda d: d.startswith((b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")),
    ".tiff": lambda d: d.startswith((b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")),
}

app = FastAPI(
    title="SatQuery AI Backend",
    description="Backend API for satellite image analysis.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    image: str = Field(min_length=1)
    query: str = ""
    analysisType: str | None = None
    options: dict = Field(default_factory=dict)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    imageId: str | None = None
    sessionId: str | None = None
    context: dict = Field(default_factory=dict)


def find_uploaded_image(image_id: str):
    try:
        UUID(image_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid image ID.")

    matches = list(UPLOAD_DIR.glob(f"{image_id}.*"))

    if not matches:
        raise HTTPException(status_code=404, detail="Uploaded image not found.")

    return matches[0]


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "SatQuery AI Backend",
        "version": "1.0.0",
    }


@app.post("/api/images/upload")
async def upload_image(image: UploadFile = File(...)):
    if not image.filename:
        raise HTTPException(status_code=400, detail="Image filename is required.")

    extension = Path(image.filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported image format.")

    image_data = await image.read(MAX_FILE_SIZE + 1)

    if not image_data:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    if len(image_data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Image exceeds the 20 MB upload limit.")

    if not IMAGE_SIGNATURES[extension](image_data):
        raise HTTPException(
            status_code=415,
            detail="Uploaded file does not match its image extension.",
        )

    image_id = str(uuid4())
    stored_filename = f"{image_id}{extension}"

    try:
        (UPLOAD_DIR / stored_filename).write_bytes(image_data)
    except OSError:
        raise HTTPException(status_code=500, detail="Unable to save uploaded image.")

    return {
        "status": "success",
        "image_id": image_id,
        "filename": Path(image.filename).name,
        "stored_filename": stored_filename,
        "content_type": image.content_type,
        "size_bytes": len(image_data),
    }


def get_inference_service():
    global _inference_service

    if _inference_service is None:
        _inference_service = SatQueryInferenceService()

    return _inference_service


def execute_analysis(image_id: str, query: str):
    image_file = find_uploaded_image(image_id)

    return get_inference_service().run_analysis(
        query=query,
        image_path=str(image_file),
        conversation=[],
    )


@app.post("/api/analysis")
async def run_analysis(payload: AnalysisRequest):
    if not payload.query.strip():
        raise HTTPException(
            status_code=422,
            detail="A natural-language analysis query is required.",
        )

    find_uploaded_image(payload.image)

    try:
        result = await run_in_threadpool(
            execute_analysis,
            payload.image,
            payload.query.strip(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis execution failed: {str(exc)}",
        ) from exc

    analysis_id = result["run_id"]
    result["analysis_id"] = analysis_id

    _analysis_records[analysis_id] = result
    _analysis_order.insert(0, analysis_id)

    return result


@app.post("/api/query")
async def send_query(payload: QueryRequest):
    if payload.imageId:
        find_uploaded_image(payload.imageId)

    raise HTTPException(
        status_code=501,
        detail="Query pipeline is not connected yet. NLP and CV integration is pending.",
    )


@app.get("/api/analysis/history")
async def get_analysis_history():
    return [
        {
            "analysis_id": analysis_id,
            "run_id": _analysis_records[analysis_id]["run_id"],
            "query": _analysis_records[analysis_id]["query"],
            "status": _analysis_records[analysis_id]["status"],
        }
        for analysis_id in _analysis_order
        if analysis_id in _analysis_records
    ]


@app.get("/api/analysis/{analysis_id}")
async def get_analysis(analysis_id: str):
    try:
        UUID(analysis_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid analysis ID.")

    result = _analysis_records.get(analysis_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found in the current backend session.",
        )

    return result
