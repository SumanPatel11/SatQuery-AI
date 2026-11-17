from pathlib import Path
import logging
import time
from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from uuid import UUID, uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from backend.services.inference_service import SatQueryInferenceService

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "storage" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 20 * 1024 * 1024

_inference_service = None
_analysis_records = {}
_analysis_order = []
_conversation_sessions = OrderedDict()
_conversation_lock = Lock()
_SESSION_TTL_SECONDS = 2 * 60 * 60
_MAX_CONVERSATION_SESSIONS = 128
_MAX_CONVERSATION_TURNS = 12

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
    second_image: str | None = None
    query: str = ""
    analysisType: str | None = None
    options: dict = Field(default_factory=dict)
    session_id: str | None = None


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    imageId: str | None = None
    secondImageId: str | None = None
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


def _conversation_snapshot(session_id, image_id, second_image_id):
    now = time.monotonic()
    with _conversation_lock:
        expired = [
            key for key, value in _conversation_sessions.items()
            if now - value.get("updated_at", now) > _SESSION_TTL_SECONDS
        ]
        for key in expired:
            _conversation_sessions.pop(key, None)

        session = _conversation_sessions.get(session_id)
        if session is None or session.get("image_id") != image_id:
            session = {
                "image_id": image_id,
                "second_image_id": second_image_id,
                "turns": [],
                "last_analysis": None,
                "updated_at": now,
            }
        elif session.get("second_image_id") != second_image_id:
            session["turns"] = [
                turn for turn in session.get("turns", [])
                if not turn.get("uses_comparison")
            ]
            previous = session.get("last_analysis")
            previous_tasks = {
                row.get("task")
                for row in (previous or {}).get("execution", {}).get("results", [])
            }
            if "BUILDING_CHANGE" in previous_tasks:
                session["last_analysis"] = None
            session["second_image_id"] = second_image_id

        session["updated_at"] = now
        _conversation_sessions[session_id] = session
        _conversation_sessions.move_to_end(session_id)
        while len(_conversation_sessions) > _MAX_CONVERSATION_SESSIONS:
            _conversation_sessions.popitem(last=False)

        turns = deepcopy(session.get("turns", []))
        conversation = []
        for turn in turns[-_MAX_CONVERSATION_TURNS:]:
            conversation.extend((
                f"User: {turn.get('query', '')}",
                f"Assistant: {turn.get('assistant_response', '')}",
            ))
        return conversation, deepcopy(session.get("last_analysis"))


def _record_conversation_turn(session_id, image_id, second_image_id, result):
    if not session_id or result.get("status") != "success":
        return
    capabilities = [
        row.get("task") for row in result.get("execution", {}).get("results", [])
    ]
    turn = {
        "query": result.get("query", ""),
        "assistant_response": result.get("assistant_response", ""),
        "capabilities": capabilities,
        "uses_comparison": "BUILDING_CHANGE" in capabilities,
    }
    with _conversation_lock:
        session = _conversation_sessions.get(session_id)
        if session is None or session.get("image_id") != image_id:
            return
        session["turns"] = (session.get("turns", []) + [turn])[-_MAX_CONVERSATION_TURNS:]
        session["last_analysis"] = deepcopy(result)
        session["second_image_id"] = second_image_id
        session["updated_at"] = time.monotonic()
        _conversation_sessions.move_to_end(session_id)


def execute_analysis(
    image_id: str,
    query: str,
    second_image_id: str | None = None,
    conversation=None,
    previous_analysis=None,
):
    image_file = find_uploaded_image(image_id)
    second_image_file = (
        find_uploaded_image(second_image_id) if second_image_id else None
    )

    return get_inference_service().run_analysis(
        query=query,
        image_path=str(image_file),
        second_image_path=(
            str(second_image_file) if second_image_file else None
        ),
        conversation=conversation or [],
        previous_analysis=previous_analysis,
    )


@app.post("/api/analysis")
async def run_analysis(payload: AnalysisRequest):
    if not payload.query.strip():
        raise HTTPException(
            status_code=422,
            detail="A natural-language analysis query is required.",
        )

    find_uploaded_image(payload.image)
    if payload.second_image:
        find_uploaded_image(payload.second_image)

    session_id = payload.session_id
    if session_id is not None and (not session_id.strip() or len(session_id) > 128):
        raise HTTPException(status_code=422, detail="Invalid conversation session ID.")
    conversation, previous_analysis = (
        _conversation_snapshot(session_id, payload.image, payload.second_image)
        if session_id else ([], None)
    )

    try:
        result = await run_in_threadpool(
            execute_analysis,
            payload.image,
            payload.query.strip(),
            payload.second_image,
            conversation,
            previous_analysis,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Analysis execution failed for image id %s", payload.image)
        raise HTTPException(
            status_code=500,
            detail="Analysis failed while processing this request. Check backend logs for details.",
        ) from exc

    analysis_id = result["run_id"]
    result["analysis_id"] = analysis_id
    if session_id:
        result["session_id"] = session_id
        _record_conversation_turn(
            session_id,
            payload.image,
            payload.second_image,
            result,
        )

    _analysis_records[analysis_id] = result
    _analysis_order.insert(0, analysis_id)

    return result


@app.post("/api/query")
async def send_query(payload: QueryRequest):
    """Chat contract: use the canonical analysis pipeline and scoped session memory.

    `imageId` and optional `secondImageId` identify uploaded inputs. The
    response has the same structured schema as `/api/analysis`, plus the
    natural answer and session ID. Conversation context is held in bounded,
    process-local memory and invalidated when image IDs change.
    """
    if not payload.imageId:
        raise HTTPException(
            status_code=422,
            detail="Upload and select a satellite image before submitting a query.",
        )

    return await run_analysis(
        AnalysisRequest(
            image=payload.imageId,
            second_image=payload.secondImageId,
            query=payload.query,
            session_id=payload.sessionId or str(uuid4()),
        )
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


@app.get("/api/analysis/{analysis_id}/flood-overlay")
async def get_flood_overlay(analysis_id: str):
    try:
        UUID(analysis_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid analysis ID.")

    analysis = _analysis_records.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    output_root = (BASE_DIR.parent / "cv" / "outputs" / "predictions").resolve()
    for item in analysis.get("execution", {}).get("results", []):
        result = item.get("result") or {}
        overlay_path = result.get("outputs", {}).get("flood_overlay_png")

        if overlay_path:
            try:
                path = Path(overlay_path).resolve()
                path.relative_to(output_root)
            except (OSError, RuntimeError, TypeError, ValueError):
                continue
            if path.is_file() and path.suffix.lower() == ".png":
                return FileResponse(
                    path,
                    media_type="image/png",
                    filename=path.name,
                )

    raise HTTPException(
        status_code=404,
        detail="Flood overlay is not available for this analysis.",
    )


@app.get("/api/analysis/{analysis_id}/change-overlay")
async def get_change_overlay(analysis_id: str):
    try:
        UUID(analysis_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid analysis ID.")

    analysis = _analysis_records.get(analysis_id)
    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found in the current backend session.",
        )

    for item in analysis.get("execution", {}).get("results", []):
        result = item.get("result") or {}
        mask_path = result.get("outputs", {}).get("change_overlay")

        if mask_path:
            path = Path(mask_path).resolve()
            output_root = (
                BASE_DIR.parent / "cv" / "outputs" / "predictions"
            ).resolve()
            if (
                path.is_relative_to(output_root)
                and path.is_file()
                and path.suffix.lower() == ".png"
            ):
                return FileResponse(
                    path,
                    media_type="image/png",
                    filename=path.name,
                )

    raise HTTPException(
        status_code=404,
        detail="Change overlay is not available for this analysis.",
    )


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
